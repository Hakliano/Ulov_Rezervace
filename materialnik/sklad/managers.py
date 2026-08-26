from django.db import models

from .tenant import get_tenant_id, tenant_bypass, require_tenant_id


class TenantQuerySet(models.QuerySet):
    def for_current_tenant(self):
        if tenant_bypass():
            return self
        tid = get_tenant_id()
        if tid is None:
            return self.none()
        return self.filter(tenant_id=tid)


class TenantManager(models.Manager):
    def get_queryset(self):
        qs = TenantQuerySet(self.model, using=self._db)
        return qs.for_current_tenant()


class UnscopedManager(models.Manager):
    """Jen provisioning, eventy a admin — nikdy ve view personálu."""

    def get_queryset(self):
        return super().get_queryset()
