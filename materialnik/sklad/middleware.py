from django.utils import timezone

from .models import StaffSession, Tenant
from .tenant import set_tenant_id, reset_tenant_id


class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.materialnik_session = None
        request.tenant = None
        ctx = set_tenant_id(None)
        try:
            token = request.COOKIES.get('materialnik_token') or ''
            if token:
                session = (
                    StaffSession.objects.select_related('tenant')
                    .filter(token=token, expires_at__gt=timezone.now())
                    .first()
                )
                if session and session.tenant.status == Tenant.STAV_ACTIVE:
                    request.materialnik_session = session
                    request.tenant = session.tenant
                    set_tenant_id(session.tenant_id)
                    self._set_rls(session.tenant_id)
            return self.get_response(request)
        finally:
            reset_tenant_id(ctx)

    def _set_rls(self, tenant_id):
        from django.db import connection
        if connection.vendor != 'postgresql':
            return
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.tenant_id', %s, true)", [str(tenant_id)])
