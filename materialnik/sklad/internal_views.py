"""Provisioning a interní API volané z FLOW (m2m)."""

import json
from uuid import UUID

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .crypto import new_hmac_key, key_hash, sign, timestamp_ok, body_canonical
from .models import (
    AuditLog,
    InboxEvent,
    ServiceMapping,
    StaffSession,
    StockLocation,
    Tenant,
    TenantCredential,
    TenantSource,
)
from .services import (
    auto_consume_from_event,
    confirm_consume,
    preview_consume,
    seed_units,
    with_tenant,
)
from .tenant import bypass_tenant, set_tenant_id


def _m2m_ok(request):
    expected = (getattr(settings, 'MATERIALNIK_M2M_KEY', '') or '').strip()
    got = (request.headers.get('X-Ulov-M2M-Key') or '').strip()
    return bool(expected) and expected == got


def _json(request):
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return {}


def _tenant_from_uuid(raw):
    try:
        uid = UUID(str(raw))
    except (TypeError, ValueError):
        return None
    return Tenant.objects.filter(pk=uid).first()


@csrf_exempt
def provision_tenant(request):
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)
    if not _m2m_ok(request):
        return JsonResponse({'detail': 'Neplatný klíč.'}, status=401)
    data = _json(request)
    try:
        uid = UUID(str(data.get('tenant_uuid')))
    except (TypeError, ValueError):
        return JsonResponse({'detail': 'Neplatný tenant.'}, status=400)
    name = (data.get('name') or 'Partner')[:200]
    external = (data.get('external_tenant_id') or '')[:80]
    source = (data.get('source') or 'modernik-flow')[:40]
    seed_units()
    tenant, created = Tenant.objects.get_or_create(
        pk=uid,
        defaults={'name_snapshot': name, 'status': Tenant.STAV_PENDING},
    )
    tenant.name_snapshot = name
    tenant.status = Tenant.STAV_ACTIVE
    tenant.activated_at = timezone.now()
    tenant.deactivated_at = None
    tenant.provisioning_error = ''
    tenant.save()
    if external:
        TenantSource.objects.get_or_create(
            tenant=tenant, source=source, external_tenant_id=external,
        )
    StockLocation.unscoped.get_or_create(
        tenant=tenant, is_default=True, defaults={'name': 'Provozovna'},
    )
    cred = TenantCredential.objects.filter(tenant=tenant, revoked_at__isnull=True).first()
    if not cred:
        secret = new_hmac_key()
        cred = TenantCredential.objects.create(
            tenant=tenant, secret=secret, key_hash=key_hash(secret),
        )
    return JsonResponse({'status': 'active', 'hmac_key': cred.secret, 'created': created})


@csrf_exempt
def deactivate_tenant(request, tenant_uuid):
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)
    if not _m2m_ok(request):
        return JsonResponse({'detail': 'Neplatný klíč.'}, status=401)
    tenant = _tenant_from_uuid(tenant_uuid)
    if not tenant:
        return JsonResponse({'detail': 'Nenalezeno.'}, status=404)
    tenant.status = Tenant.STAV_INACTIVE
    tenant.deactivated_at = timezone.now()
    tenant.save(update_fields=['status', 'deactivated_at'])
    StaffSession.objects.filter(tenant=tenant).delete()
    return JsonResponse({'status': 'inactive'})


def _bind_tenant_or_401(data):
    tenant = _tenant_from_uuid(data.get('tenant_uuid'))
    if not tenant:
        return None, JsonResponse({'detail': 'Nenalezeno.'}, status=404)
    if tenant.status != Tenant.STAV_ACTIVE:
        AuditLog.objects.create(
            tenant=tenant, action='tenant_inactive', meta={'tenant': str(tenant.id)},
        )
        return None, JsonResponse({'detail': 'Nenalezeno.'}, status=404)
    hmac_key = data.get('hmac_key') or ''
    cred = TenantCredential.objects.filter(tenant=tenant, revoked_at__isnull=True).first()
    if not cred or hmac_key != cred.secret:
        AuditLog.objects.create(tenant=tenant, action='bad_hmac_key')
        return None, JsonResponse({'detail': 'Neplatný klíč.'}, status=401)
    set_tenant_id(tenant.id)
    return tenant, None


@csrf_exempt
def consume_preview(request):
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)
    if not _m2m_ok(request):
        return JsonResponse({'detail': 'Neplatný klíč.'}, status=401)
    data = _json(request)
    tenant, err = _bind_tenant_or_401(data)
    if err:
        return err
    return JsonResponse(preview_consume(tenant, data))


@csrf_exempt
def consume_confirm(request):
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)
    if not _m2m_ok(request):
        return JsonResponse({'detail': 'Neplatný klíč.'}, status=401)
    data = _json(request)
    tenant, err = _bind_tenant_or_401(data)
    if err:
        return err
    return JsonResponse(confirm_consume(tenant, data))


@csrf_exempt
def ingest_event(request):
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)
    raw_body = request.body or b'{}'
    try:
        payload = json.loads(raw_body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Neplatný JSON.'}, status=400)

    event_id = (payload.get('event_id') or '')[:64]
    timestamp = request.headers.get('X-Timestamp') or payload.get('occurred_at') or ''
    signature = (request.headers.get('X-Signature') or '').strip()
    if not event_id:
        return JsonResponse({'detail': 'Chybí event_id.'}, status=400)

    existing = InboxEvent.objects.filter(event_id=event_id).first()
    if existing:
        return JsonResponse({'ok': True, 'duplicate': True})

    if not timestamp_ok(timestamp):
        AuditLog.objects.create(action='expired_request', meta={'event_id': event_id})
        return JsonResponse({'detail': 'Expirovaný požadavek.'}, status=401)

    tenant_uuid = payload.get('tenant_uuid')
    tenant = _tenant_from_uuid(tenant_uuid)
    if not tenant or tenant.status != Tenant.STAV_ACTIVE:
        InboxEvent.objects.create(
            event_id=event_id, event_type=payload.get('event_type') or '',
            payload=payload, status=InboxEvent.STAV_REJECTED, reject_reason='tenant_inactive',
        )
        AuditLog.objects.create(tenant=tenant, action='tenant_inactive', meta={'event_id': event_id})
        return JsonResponse({'detail': 'Nenalezeno.'}, status=404)

    cred = TenantCredential.objects.filter(tenant=tenant, revoked_at__isnull=True).first()
    expected = sign(cred.secret, timestamp, event_id, raw_body) if cred else ''
    if not cred or not signature or signature != expected:
        # zkus i canonical body — FLOW posílá stejný JSON
        expected2 = sign(cred.secret, timestamp, event_id, body_canonical(payload)) if cred else ''
        if signature != expected2:
            AuditLog.objects.create(tenant=tenant, action='bad_signature', meta={'event_id': event_id})
            InboxEvent.objects.create(
                event_id=event_id, tenant=tenant, payload=payload,
                event_type=payload.get('event_type') or '',
                status=InboxEvent.STAV_REJECTED, reject_reason='bad_signature',
            )
            return JsonResponse({'detail': 'Neplatný podpis.'}, status=401)

    set_tenant_id(tenant.id)
    inner = payload.get('payload') or {}
    services = inner.get('services') or []
    for svc in services:
        ext = svc.get('external_service_id') or ''
        mapping = ServiceMapping.objects.filter(
            tenant=tenant, external_service_id=ext,
        ).first()
        if not mapping:
            AuditLog.objects.create(
                tenant=tenant,
                action='service_not_in_tenant',
                meta={'event_id': event_id, 'external_service_id': ext},
            )
            InboxEvent.objects.create(
                event_id=event_id, tenant=tenant, payload=payload,
                event_type=payload.get('event_type') or '',
                status=InboxEvent.STAV_REJECTED, reject_reason='service_not_in_tenant',
            )
            return JsonResponse({'detail': 'Služba nepatří tenantovi.', 'rejected': True}, status=403)

    result = auto_consume_from_event(tenant, payload, event_id)
    InboxEvent.objects.create(
        event_id=event_id, tenant=tenant, payload=payload,
        event_type=payload.get('event_type') or 'service.completed',
        status=InboxEvent.STAV_DUPLICATE if result.get('duplicate') else InboxEvent.STAV_PROCESSED,
        processed_at=timezone.now(),
    )
    return JsonResponse(result)
