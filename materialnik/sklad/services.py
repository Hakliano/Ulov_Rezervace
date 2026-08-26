from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.db.models import Sum
from django.utils import timezone

from .models import (
    Alert,
    InboxEvent,
    Material,
    Recipe,
    RecipeLine,
    ServiceMapping,
    ShoppingListItem,
    StockLocation,
    StockMovement,
    Tenant,
    Unit,
)
from .tenant import set_tenant_id, bypass_tenant


def stock_qty(material):
    agg = StockMovement.objects.filter(material=material).aggregate(s=Sum('quantity_delta'))
    return agg['s'] or Decimal('0')


def _dec(value, default='0'):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return Decimal(default)


def ensure_default_location(tenant):
    loc = StockLocation.unscoped.filter(tenant=tenant, is_default=True).first()
    if loc:
        return loc
    return StockLocation.unscoped.create(tenant=tenant, name='Provozovna', is_default=True)


def seed_units():
    for code, name in (('ml', 'mililitr'), ('l', 'litr'), ('g', 'gram'), ('kg', 'kilogram'), ('ks', 'kus')):
        Unit.objects.get_or_create(code=code, defaults={'name': name})


def audit(tenant, action, actor='system', meta=None):
    from .models import AuditLog
    AuditLog.objects.create(tenant=tenant, action=action, actor=actor, meta=meta or {})


def with_tenant(tenant_id):
    set_tenant_id(tenant_id)


def _qty_str(value):
    if value is None or value == '':
        return ''
    d = _dec(value)
    text = format(d.normalize(), 'f')
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return text


def mapping_for_service(tenant, external_service_id, source='modernik-flow'):
    return ServiceMapping.objects.filter(
        tenant=tenant,
        source=source,
        external_service_id=external_service_id,
    ).first()


def recipe_lines_for_services(tenant, services):
    """services: [{external_service_id, name, quantity}]"""
    out = []
    for svc in services or []:
        ext = svc.get('external_service_id') or ''
        mapping = mapping_for_service(tenant, ext)
        if not mapping or mapping.status != ServiceMapping.STAV_ACTIVE:
            continue
        try:
            recipe = mapping.recipe
        except Recipe.DoesNotExist:
            continue
        if not recipe.active:
            continue
        for line in recipe.lines.select_related('material', 'unit'):
            typical = None
            if line.quantity is not None:
                typical = line.quantity * _dec(svc.get('quantity') or 1, '1')
            out.append({
                'material_id': str(line.material_id),
                'material_name': line.material.name,
                'service_name': mapping.name_snapshot or svc.get('name') or '',
                'external_service_id': ext,
                'recipe_qty': _qty_str(typical) if typical is not None else '',
                'actual_qty': '',
                'unit': line.unit.code,
                'mapping_id': mapping.id,
            })
    return out


def _ensure_open_shopping(material, qty):
    if qty >= material.min_quantity:
        ShoppingListItem.objects.filter(
            material=material, status=ShoppingListItem.STAV_OPEN, origin=ShoppingListItem.ORIGIN_AUTO,
        ).update(status=ShoppingListItem.STAV_DISMISSED, resolved_at=timezone.now())
        Alert.objects.filter(material=material, status=Alert.STAV_OPEN).update(
            status=Alert.STAV_RESOLVED, resolved_at=timezone.now(),
        )
        return
    need = material.min_quantity - qty
    item, created = ShoppingListItem.objects.get_or_create(
        tenant_id=material.tenant_id,
        material=material,
        status=ShoppingListItem.STAV_OPEN,
        origin=ShoppingListItem.ORIGIN_AUTO,
        defaults={
            'quantity_to_buy': need,
            'unit': material.unit,
            'supplier': material.primary_supplier,
        },
    )
    if not created:
        item.quantity_to_buy = need
        item.save(update_fields=['quantity_to_buy'])
    alert_type = Alert.TYP_ZERO if qty <= 0 else (
        Alert.TYP_CRITICAL
        if material.critical_quantity is not None and qty <= material.critical_quantity
        else Alert.TYP_LOW
    )
    Alert.objects.get_or_create(
        tenant_id=material.tenant_id,
        material=material,
        type=alert_type,
        status=Alert.STAV_OPEN,
        defaults={'payload': {'qty': str(qty)}},
    )


def apply_lines(tenant, lines, *, movement_type, event_id='', reservation_ref='', actor='system', reason=''):
    created = []
    for raw in lines:
        material = Material.objects.filter(pk=raw.get('material_id')).first()
        if not material or material.tenant_id != tenant.id:
            continue
        qty = _dec(raw.get('quantity') if raw.get('quantity') is not None else raw.get('actual_qty'))
        if movement_type == StockMovement.TYP_INVENTORY:
            current = stock_qty(material)
            delta = qty - current
            if delta == 0:
                continue
        elif 'signed_delta' in raw:
            delta = _dec(raw.get('signed_delta'))
            if delta == 0:
                continue
        else:
            if qty == 0:
                continue
            delta = -abs(qty)
        mapping = None
        ext = raw.get('external_service_id')
        if ext:
            mapping = mapping_for_service(tenant, ext)
        mv = StockMovement.objects.create(
            tenant=tenant,
            material=material,
            quantity_delta=delta,
            unit=material.unit,
            type=movement_type,
            reason=reason,
            source='modernik-flow' if event_id else 'standalone',
            external_event_id=event_id or '',
            reservation_ref=reservation_ref or '',
            service_mapping=mapping,
            created_by_type='user' if actor != 'system' else 'system',
            created_by_user_id=str(actor) if actor != 'system' else '',
        )
        created.append(mv)
        _ensure_open_shopping(material, stock_qty(material))
    return created


def reservation_has_consume(tenant, reservation_ref):
    if not reservation_ref:
        return False
    return StockMovement.objects.filter(
        tenant=tenant,
        reservation_ref=reservation_ref,
        type__in=[StockMovement.TYP_AUTO, StockMovement.TYP_CONFIRM],
    ).exists()


def preview_consume(tenant, payload):
    services = payload.get('services') or []
    lines = recipe_lines_for_services(tenant, services)
    return {'lines': lines, 'empty': not lines}


def confirm_consume(tenant, payload, actor='user'):
    reservation_ref = payload.get('reservation_ref') or ''
    event_id = payload.get('event_id') or (f'confirm:{reservation_ref}' if reservation_ref else '')
    lines = payload.get('lines') or []
    normalized = []
    for line in lines:
        normalized.append({
            'material_id': line.get('material_id'),
            'quantity': line.get('quantity') or line.get('actual_qty'),
            'external_service_id': line.get('external_service_id'),
        })
    if reservation_has_consume(tenant, reservation_ref):
        # korekce vůči už zapsané auto spotřebě
        existing = list(StockMovement.objects.filter(
            tenant=tenant, reservation_ref=reservation_ref,
        ))
        by_mat = {}
        for mv in existing:
            by_mat[mv.material_id] = by_mat.get(mv.material_id, Decimal('0')) + mv.quantity_delta
        adjust = []
        for line in normalized:
            mid = int(line['material_id']) if str(line.get('material_id') or '').isdigit() else line.get('material_id')
            want = -abs(_dec(line.get('quantity')))
            have = by_mat.get(mid, by_mat.get(int(mid) if str(mid).isdigit() else mid, Decimal('0')))
            delta = want - have
            if delta == 0:
                continue
            adjust.append({
                'material_id': mid,
                'signed_delta': delta,
                'external_service_id': line.get('external_service_id'),
            })
        created = apply_lines(
            tenant, adjust,
            movement_type=StockMovement.TYP_MANUAL,
            event_id=event_id + ':adj' if event_id else '',
            reservation_ref=reservation_ref,
            actor=actor,
            reason='Korekce skutečné spotřeby',
        )
        return {'ok': True, 'adjusted': True, 'movements': len(created)}
    created = apply_lines(
        tenant, normalized,
        movement_type=StockMovement.TYP_CONFIRM,
        event_id=event_id,
        reservation_ref=reservation_ref,
        actor=actor,
        reason='Potvrzená spotřeba',
    )
    return {'ok': True, 'adjusted': False, 'movements': len(created)}


def auto_consume_from_event(tenant, payload, event_id):
    inner = payload.get('payload') or payload
    reservation_ref = inner.get('reservation_ref') or ''
    if reservation_has_consume(tenant, reservation_ref):
        return {'ok': True, 'duplicate': True}
    # Paleta ke službě není předpis — množství zadá personál po práci.
    return {'ok': True, 'duplicate': False, 'movements': 0, 'awaiting_confirm': True}
