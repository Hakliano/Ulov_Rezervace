from decimal import Decimal, InvalidOperation
from functools import wraps
from uuid import uuid4

from django.contrib import messages
from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from .models import (
    Alert,
    Category,
    Material,
    Recipe,
    RecipeLine,
    ServiceMapping,
    ShoppingListItem,
    StaffSession,
    StockMovement,
    Supplier,
    Tenant,
    Unit,
)
from .services import stock_qty, apply_lines, seed_units
from .tenant import set_tenant_id
from .ulov import UlovAuthError, ulov_catalog, ulov_session


def login_required_sklad(view):
    @wraps(view)
    def inner(request, *args, **kwargs):
        if not getattr(request, 'materialnik_session', None):
            return redirect('sklad:login')
        return view(request, *args, **kwargs)
    return inner


def _units():
    seed_units()
    return Unit.objects.all().order_by('code')


@require_http_methods(['GET', 'POST'])
def login_view(request):
    if request.method == 'GET':
        if getattr(request, 'materialnik_session', None):
            return redirect('sklad:home')
        return render(request, 'sklad/login.html')
    email = (request.POST.get('email') or '').strip()
    password = request.POST.get('password') or ''
    try:
        data = ulov_session(email, password)
    except UlovAuthError as exc:
        return render(request, 'sklad/login.html', {'error': exc.detail, 'email': email})
    tenant = Tenant.objects.filter(pk=data['tenant_uuid'], status=Tenant.STAV_ACTIVE).first()
    if not tenant:
        return render(
            request, 'sklad/login.html',
            {'error': 'Materiálník pro tento salon ještě není zapnutý.', 'email': email},
        )
    session = StaffSession.issue(tenant, data.get('staff') or {})
    response = redirect('sklad:home')
    response.set_cookie(
        'materialnik_token', session.token,
        httponly=True, samesite='Lax', max_age=14 * 24 * 3600,
    )
    return response


@require_POST
def logout_view(request):
    token = request.COOKIES.get('materialnik_token')
    if token:
        StaffSession.objects.filter(token=token).delete()
    response = redirect('sklad:login')
    response.delete_cookie('materialnik_token')
    return response


def _row_status(material, qty):
    min_q = material.min_quantity or Decimal('0')
    crit = material.critical_quantity
    if qty <= 0:
        return 'critical', 'Kriticky nízké', 4
    if crit is not None and qty <= crit:
        return 'critical', 'Kriticky nízké', 12
    if min_q > 0 and qty < (min_q * Decimal('0.5')):
        return 'low', 'Nízké', 28
    if min_q > 0 and qty < min_q:
        return 'warn', 'Pod minimem', max(8, int((qty / min_q) * 100))
    pct = 100
    if min_q > 0:
        pct = min(100, int((qty / min_q) * 100))
    return 'ok', 'V pořádku', pct


@login_required_sklad
def home(request):
    from datetime import timedelta
    from django.db.models.functions import TruncDate
    from django.utils import timezone

    materials = list(
        Material.objects.filter(active=True).select_related('unit', 'primary_supplier', 'category')
    )
    rows = []
    below = []
    critical = 0
    stock_value = Decimal('0')
    for m in materials:
        qty = stock_qty(m)
        kind, label, pct = _row_status(m, qty)
        item = {
            'm': m, 'qty': qty, 'below': kind != 'ok',
            'status': kind, 'status_label': label, 'pct': pct,
        }
        rows.append(item)
        if kind != 'ok':
            below.append(item)
        if kind == 'critical':
            critical += 1
        if m.last_purchase_price:
            stock_value += qty * m.last_purchase_price

    since = timezone.now() - timedelta(days=7)
    consume_qs = (
        StockMovement.objects.filter(created_at__gte=since, quantity_delta__lt=0)
        .values('material_id', 'material__name', 'unit__code')
        .annotate(total=Sum('quantity_delta'))
        .order_by('total')[:5]
    )
    top_consumed = []
    max_abs = Decimal('1')
    for row in consume_qs:
        amount = abs(row['total'] or 0)
        max_abs = max(max_abs, amount)
        top_consumed.append({
            'name': row['material__name'],
            'amount': amount,
            'unit': row['unit__code'],
        })
    for item in top_consumed:
        item['pct'] = int((item['amount'] / max_abs) * 100)

    day_totals = {
        row['day']: abs(row['total'] or 0)
        for row in (
            StockMovement.objects.filter(created_at__gte=since, quantity_delta__lt=0)
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(total=Sum('quantity_delta'))
        )
        if row['day']
    }
    labels = ['Po', 'Út', 'St', 'Čt', 'Pá', 'So', 'Ne']
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    week_vals = []
    for i in range(7):
        d = week_start + timedelta(days=i)
        week_vals.append(day_totals.get(d, Decimal('0')))
    week_max = max(week_vals) if any(week_vals) else Decimal('1')
    days = [
        {'label': labels[i], 'value': week_vals[i], 'pct': int((week_vals[i] / week_max) * 100)}
        for i in range(7)
    ]

    alerts = Alert.objects.filter(status=Alert.STAV_OPEN).select_related('material')[:6]
    shopping_qs = ShoppingListItem.objects.filter(status=ShoppingListItem.STAV_OPEN).select_related(
        'material', 'unit', 'supplier',
    )
    shopping_count = shopping_qs.count()
    return render(request, 'sklad/home.html', {
        'below': below[:8],
        'alerts': alerts,
        'shopping': list(shopping_qs[:6]),
        'kpi_value': stock_value,
        'kpi_value_fmt': f'{int(stock_value):,}'.replace(',', '\u00a0') if stock_value else '',
        'kpi_below': len(below),
        'kpi_total': len(rows),
        'kpi_critical': critical,
        'kpi_shopping': shopping_count,
        'top_consumed': top_consumed,
        'week_days': days,
        'page_title': 'Přehled',
    })


@login_required_sklad
def materials(request):
    qs = Material.objects.select_related('unit', 'category', 'primary_supplier')
    rows = []
    for m in qs:
        qty = stock_qty(m)
        kind, label, pct = _row_status(m, qty)
        rows.append({'m': m, 'qty': qty, 'status': kind, 'status_label': label, 'pct': pct})
    return render(request, 'sklad/materials.html', {'rows': rows, 'page_title': 'Materiály'})


@login_required_sklad
@require_http_methods(['GET', 'POST'])
def material_form(request, pk=None):
    material = get_object_or_404(Material, pk=pk) if pk else None
    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        if not name:
            messages.error(request, 'Zadejte název materiálu.')
        else:
            unit = get_object_or_404(Unit, pk=request.POST.get('unit'))
            supplier_id = request.POST.get('supplier') or ''
            cat_id = request.POST.get('category') or ''
            data = {
                'name': name,
                'unit': unit,
                'sku': (request.POST.get('sku') or '')[:80],
                'barcode': (request.POST.get('barcode') or '')[:80],
                'min_quantity': _dec(request.POST.get('min_quantity')),
                'critical_quantity': (
                    _dec(request.POST.get('critical_quantity'))
                    if (request.POST.get('critical_quantity') or '').strip() else None
                ),
                'last_purchase_price': _dec(request.POST.get('last_purchase_price')) or None,
                'note': request.POST.get('note') or '',
                'active': request.POST.get('active') == 'on',
                'primary_supplier': Supplier.objects.filter(pk=supplier_id).first() if supplier_id else None,
                'category': Category.objects.filter(pk=cat_id).first() if cat_id else None,
            }
            if material:
                for k, v in data.items():
                    setattr(material, k, v)
                material.save()
            else:
                Material.objects.create(tenant=request.tenant, **data)
            messages.success(request, 'Materiál uložen.')
            return redirect('sklad:materials')
    return render(request, 'sklad/material_form.html', {
        'material': material,
        'units': _units(),
        'suppliers': Supplier.objects.filter(active=True),
        'categories': Category.objects.all(),
        'page_title': 'Materiály',
    })


@login_required_sklad
@require_http_methods(['GET', 'POST'])
def suppliers(request):
    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        if name:
            Supplier.objects.create(
                tenant=request.tenant, name=name, note=request.POST.get('note') or '',
            )
            messages.success(request, 'Dodavatel přidán.')
            return redirect('sklad:suppliers')
    return render(request, 'sklad/suppliers.html', {
        'suppliers': Supplier.objects.all(),
        'page_title': 'Dodavatelé',
    })


@login_required_sklad
@require_http_methods(['GET', 'POST'])
def consume(request):
    materials = Material.objects.filter(active=True).select_related('unit')
    mappings = ServiceMapping.objects.filter(status=ServiceMapping.STAV_ACTIVE)
    if request.method == 'POST':
        mid = request.POST.get('material')
        qty = _dec(request.POST.get('quantity'))
        note = request.POST.get('note') or ''
        material = get_object_or_404(Material, pk=mid)
        if qty <= 0:
            messages.error(request, 'Zadejte kladné množství.')
        else:
            apply_lines(
                request.tenant,
                [{'material_id': material.pk, 'quantity': qty}],
                movement_type=StockMovement.TYP_CONFIRM,
                actor=request.materialnik_session.staff_name,
                reason=note or 'Ruční odečet',
            )
            messages.success(request, f'Odečteno {qty} {material.unit.code} z {material.name}.')
            return redirect('sklad:consume')
    return render(request, 'sklad/consume.html', {
        'materials': materials,
        'services': mappings,
        'page_title': 'Odečet spotřeby',
    })


@login_required_sklad
@require_http_methods(['GET', 'POST'])
def inventory(request):
    materials = Material.objects.filter(active=True).select_related('unit')
    rows = [{'m': m, 'qty': stock_qty(m)} for m in materials]
    if request.method == 'POST':
        mid = request.POST.get('material')
        actual = _dec(request.POST.get('actual'))
        reason = request.POST.get('reason') or 'Inventura'
        material = get_object_or_404(Material, pk=mid)
        apply_lines(
            request.tenant,
            [{'material_id': material.pk, 'quantity': actual}],
            movement_type=StockMovement.TYP_INVENTORY,
            actor=request.materialnik_session.staff_name,
            reason=reason,
        )
        messages.success(request, 'Inventura uložena.')
        return redirect('sklad:inventory')
    return render(request, 'sklad/inventory.html', {'rows': rows, 'page_title': 'Inventura'})


@login_required_sklad
@require_http_methods(['GET', 'POST'])
def shopping(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        pk = request.POST.get('pk')
        if action == 'add':
            material = get_object_or_404(Material, pk=request.POST.get('material'))
            ShoppingListItem.objects.create(
                tenant=request.tenant,
                material=material,
                quantity_to_buy=_dec(request.POST.get('quantity')) or Decimal('1'),
                unit=material.unit,
                supplier=material.primary_supplier,
                origin=ShoppingListItem.ORIGIN_MANUAL,
            )
            messages.success(request, 'Položka přidána na nákupní seznam.')
        elif action in ('bought', 'dismissed') and pk:
            item = get_object_or_404(ShoppingListItem, pk=pk, status=ShoppingListItem.STAV_OPEN)
            item.status = (
                ShoppingListItem.STAV_BOUGHT if action == 'bought' else ShoppingListItem.STAV_DISMISSED
            )
            from django.utils import timezone
            item.resolved_at = timezone.now()
            item.save(update_fields=['status', 'resolved_at'])
        return redirect('sklad:shopping')
    items = ShoppingListItem.objects.filter(status=ShoppingListItem.STAV_OPEN).select_related(
        'material', 'unit', 'supplier',
    )
    return render(request, 'sklad/shopping.html', {
        'items': items,
        'materials': Material.objects.filter(active=True),
        'page_title': 'Nákupní seznam',
    })


@login_required_sklad
def movements(request):
    qs = StockMovement.objects.select_related('material', 'unit')[:200]
    return render(request, 'sklad/movements.html', {'movements': qs, 'page_title': 'Pohyby / Historie'})


@login_required_sklad
def recipes(request):
    _sync_catalog(request.tenant)
    recipes_qs = (
        Recipe.objects.select_related('service_mapping')
        .prefetch_related('lines__material', 'lines__unit')
        .order_by('service_mapping__name_snapshot')
    )
    used_ids = {r.service_mapping_id for r in recipes_qs}
    unused = ServiceMapping.objects.exclude(pk__in=used_ids).order_by('name_snapshot')
    return render(request, 'sklad/recipes.html', {
        'recipes': recipes_qs,
        'unused_mappings': unused,
        'page_title': 'Materiály ke službě',
    })


def _unused_mappings(recipe=None):
    qs = ServiceMapping.objects.order_by('name_snapshot')
    if recipe:
        return qs.filter(pk=recipe.service_mapping_id)
    used = Recipe.objects.values_list('service_mapping_id', flat=True)
    return qs.exclude(pk__in=used)


def _posted_recipe_lines(request):
    rows = []
    for mid, qraw in zip(request.POST.getlist('material'), request.POST.getlist('quantity')):
        rows.append({'material_id': str(mid or ''), 'quantity': qraw or ''})
    return rows or [{'material_id': '', 'quantity': ''}]


@login_required_sklad
@require_http_methods(['GET', 'POST'])
def recipe_form(request, pk=None):
    recipe = get_object_or_404(Recipe, pk=pk) if pk else None
    materials = Material.objects.select_related('unit').order_by('name')
    unused = _unused_mappings(recipe)

    def ctx(lines=None, mapping_id='', custom_name=''):
        if lines is None:
            if recipe:
                lines = [
                    {'material_id': str(line.material_id), 'quantity': line.quantity}
                    for line in recipe.lines.all()
                ] or [{'material_id': '', 'quantity': ''}]
            else:
                lines = [{'material_id': '', 'quantity': ''}]
        return {
            'recipe': recipe,
            'materials': materials,
            'unused_mappings': unused,
            'lines': lines,
            'mapping_id': str(mapping_id or (recipe.service_mapping_id if recipe else '')),
            'custom_name': custom_name,
            'page_title': 'Materiály ke službě',
        }

    if request.method == 'POST':
        if recipe and request.POST.get('action') == 'delete':
            recipe.delete()
            messages.success(request, 'Seznam smazán.')
            return redirect('sklad:recipes')

        posted = _posted_recipe_lines(request)
        mapping_id = request.POST.get('mapping') or ''
        custom_name = (request.POST.get('custom_name') or '').strip()

        mapping = None
        if recipe:
            mapping = recipe.service_mapping
        elif mapping_id:
            mapping = get_object_or_404(ServiceMapping, pk=mapping_id)
            existing = Recipe.objects.filter(service_mapping=mapping).first()
            if existing:
                messages.error(request, 'Tato služba už seznam má — otevřeli jsme úpravu.')
                return redirect('sklad:recipe_edit', pk=existing.pk)
        elif custom_name:
            mapping = ServiceMapping.objects.create(
                tenant=request.tenant,
                source='manual',
                external_service_id=f'manual:{uuid4().hex[:12]}',
                name_snapshot=custom_name[:200],
                status=ServiceMapping.STAV_ACTIVE,
            )
        else:
            messages.error(request, 'Vyberte službu z ceníku, nebo zadejte vlastní název.')
            return render(request, 'sklad/recipe_form.html', ctx(posted, mapping_id, custom_name))

        parsed = []
        seen = set()
        for row in posted:
            if not row['material_id']:
                continue
            try:
                mid = int(row['material_id'])
            except (TypeError, ValueError):
                continue
            qty = None
            qraw = (row['quantity'] or '').strip()
            if qraw:
                qty = _dec(qraw)
                if qty <= 0:
                    qty = None
            if mid in seen:
                messages.error(request, 'Stejný materiál je v seznamu víckrát. Sloučte ho do jednoho řádku.')
                return render(request, 'sklad/recipe_form.html', ctx(posted, mapping_id, custom_name))
            seen.add(mid)
            material = get_object_or_404(Material, pk=mid)
            parsed.append((material, qty))

        with transaction.atomic():
            if not recipe:
                recipe = Recipe.objects.create(
                    tenant=request.tenant, service_mapping=mapping, active=True,
                )
            recipe.lines.all().delete()
            RecipeLine.objects.bulk_create([
                RecipeLine(
                    tenant=request.tenant,
                    recipe=recipe,
                    material=material,
                    quantity=qty,
                    unit=material.unit,
                )
                for material, qty in parsed
            ])
        messages.success(request, 'Seznam materiálů uložen.')
        return redirect('sklad:recipes')

    return render(request, 'sklad/recipe_form.html', ctx())


def _sync_catalog(tenant):
    services = ulov_catalog(str(tenant.id))
    for svc in services:
        ServiceMapping.objects.update_or_create(
            tenant=tenant,
            source='modernik-flow',
            external_service_id=svc['external_service_id'],
            defaults={
                'name_snapshot': svc.get('name') or '',
                'status': (
                    ServiceMapping.STAV_ACTIVE if svc.get('active', True)
                    else ServiceMapping.STAV_INACTIVE
                ),
            },
        )


@login_required_sklad
def alerts(request):
    items = Alert.objects.filter(status=Alert.STAV_OPEN).select_related('material')
    return render(request, 'sklad/alerts.html', {'items': items, 'page_title': 'Upozornění'})


@login_required_sklad
@require_http_methods(['GET', 'POST'])
def categories(request):
    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        if name:
            Category.objects.create(tenant=request.tenant, name=name)
            messages.success(request, 'Kategorie přidána.')
            return redirect('sklad:categories')
    return render(request, 'sklad/categories.html', {
        'categories': Category.objects.all(),
        'page_title': 'Kategorie',
    })


@login_required_sklad
def units(request):
    return render(request, 'sklad/units.html', {'units': _units(), 'page_title': 'Jednotky'})


@login_required_sklad
def reports(request):
    return redirect('sklad:home')


def _dec(value):
    try:
        if value in (None, ''):
            return Decimal('0')
        return Decimal(str(value).replace(',', '.'))
    except (InvalidOperation, TypeError):
        return Decimal('0')
