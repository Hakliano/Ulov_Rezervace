import secrets
from datetime import timedelta
from decimal import Decimal

from django.db import models
from django.utils import timezone

from .managers import TenantManager, UnscopedManager


class Tenant(models.Model):
    STAV_PENDING = 'pending'
    STAV_ACTIVE = 'active'
    STAV_INACTIVE = 'inactive'
    STAV_ERROR = 'error'
    STAVY = [
        (STAV_PENDING, 'Zapíná se'),
        (STAV_ACTIVE, 'Aktivní'),
        (STAV_INACTIVE, 'Vypnuto'),
        (STAV_ERROR, 'Chyba'),
    ]

    id = models.UUIDField(primary_key=True)
    name_snapshot = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STAVY, default=STAV_PENDING, db_index=True)
    provisioning_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)

    objects = UnscopedManager()

    def __str__(self):
        return f'{self.name_snapshot} ({self.status})'


class TenantSource(models.Model):
    tenant = models.ForeignKey(Tenant, related_name='sources', on_delete=models.CASCADE)
    source = models.CharField(max_length=40, default='modernik-flow')
    external_tenant_id = models.CharField(max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['source', 'external_tenant_id'],
                name='unique_source_external_tenant',
            ),
        ]


class TenantCredential(models.Model):
    tenant = models.ForeignKey(Tenant, related_name='credentials', on_delete=models.CASCADE)
    kid = models.CharField(max_length=40, default='tenant')
    secret = models.CharField(max_length=128)
    key_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    objects = UnscopedManager()


class StaffSession(models.Model):
    tenant = models.ForeignKey(Tenant, related_name='sessions', on_delete=models.CASCADE)
    token = models.CharField(max_length=64, unique=True, db_index=True)
    staff_external_id = models.CharField(max_length=40)
    staff_name = models.CharField(max_length=120)
    role = models.CharField(max_length=30, blank=True)
    je_majitel = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UnscopedManager()

    @classmethod
    def issue(cls, tenant, staff, days=14):
        return cls.objects.create(
            tenant=tenant,
            token=secrets.token_hex(32),
            staff_external_id=str(staff.get('id') or ''),
            staff_name=staff.get('jmeno') or '',
            role=staff.get('role') or '',
            je_majitel=bool(staff.get('je_majitel')),
            expires_at=timezone.now() + timedelta(days=days),
        )


class Unit(models.Model):
    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=40)

    objects = UnscopedManager()

    def __str__(self):
        return self.code


class TenantModel(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)

    objects = TenantManager()
    unscoped = UnscopedManager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        from .tenant import get_tenant_id, tenant_bypass
        tid = get_tenant_id()
        if tid and self.tenant_id and self.tenant_id != tid and not tenant_bypass():
            raise ValueError('Nelze uložit záznam jiného tenanta.')
        if tid and not self.tenant_id:
            self.tenant_id = tid
        super().save(*args, **kwargs)


class Category(TenantModel):
    name = models.CharField(max_length=80)
    sort = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['sort', 'name']


class Supplier(TenantModel):
    name = models.CharField(max_length=120)
    note = models.CharField(max_length=300, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']


class StockLocation(TenantModel):
    name = models.CharField(max_length=80, default='Provozovna')
    is_default = models.BooleanField(default=True)


class Material(TenantModel):
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL)
    primary_supplier = models.ForeignKey(Supplier, null=True, blank=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=160)
    sku = models.CharField(max_length=80, blank=True)
    barcode = models.CharField(max_length=80, blank=True)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT)
    min_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal('0'))
    critical_quantity = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    last_purchase_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    note = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class ServiceMapping(TenantModel):
    STAV_ACTIVE = 'active'
    STAV_INACTIVE = 'inactive'
    STAV_MISSING = 'missing'

    source = models.CharField(max_length=40, default='modernik-flow')
    external_service_id = models.CharField(max_length=80)
    name_snapshot = models.CharField(max_length=200)
    status = models.CharField(max_length=20, default=STAV_ACTIVE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'source', 'external_service_id'],
                name='unique_tenant_service_mapping',
            ),
        ]


class Recipe(TenantModel):
    service_mapping = models.OneToOneField(
        ServiceMapping, related_name='recipe', on_delete=models.CASCADE,
    )
    active = models.BooleanField(default=True)


class RecipeLine(TenantModel):
    recipe = models.ForeignKey(Recipe, related_name='lines', on_delete=models.CASCADE)
    material = models.ForeignKey(Material, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT)


class StockMovement(TenantModel):
    TYP_AUTO = 'auto_consume'
    TYP_CONFIRM = 'consume_confirm'
    TYP_MANUAL = 'manual_adjust'
    TYP_INVENTORY = 'inventory'
    TYP_PURCHASE = 'purchase_receipt'
    TYP_REVERSE = 'reverse'
    TYPY = [
        (TYP_AUTO, 'Automatická spotřeba'),
        (TYP_CONFIRM, 'Potvrzená spotřeba'),
        (TYP_MANUAL, 'Ruční korekce'),
        (TYP_INVENTORY, 'Inventura'),
        (TYP_PURCHASE, 'Příjem'),
        (TYP_REVERSE, 'Storno pohybu'),
    ]

    material = models.ForeignKey(Material, related_name='movements', on_delete=models.PROTECT)
    location = models.ForeignKey(StockLocation, null=True, blank=True, on_delete=models.SET_NULL)
    quantity_delta = models.DecimalField(max_digits=12, decimal_places=3)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT)
    type = models.CharField(max_length=30, choices=TYPY)
    reason = models.CharField(max_length=200, blank=True)
    note = models.CharField(max_length=300, blank=True)
    source = models.CharField(max_length=40, blank=True)
    external_event_id = models.CharField(max_length=80, blank=True, db_index=True)
    reservation_ref = models.CharField(max_length=80, blank=True, db_index=True)
    service_mapping = models.ForeignKey(
        ServiceMapping, null=True, blank=True, on_delete=models.SET_NULL,
    )
    created_by_type = models.CharField(max_length=20, default='system')
    created_by_user_id = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class ShoppingListItem(TenantModel):
    STAV_OPEN = 'open'
    STAV_BOUGHT = 'bought'
    STAV_DISMISSED = 'dismissed'
    ORIGIN_AUTO = 'auto_min'
    ORIGIN_MANUAL = 'manual'

    material = models.ForeignKey(Material, related_name='shopping', on_delete=models.CASCADE)
    supplier = models.ForeignKey(Supplier, null=True, blank=True, on_delete=models.SET_NULL)
    quantity_to_buy = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal('0'))
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, default=STAV_OPEN, db_index=True)
    origin = models.CharField(max_length=20, default=ORIGIN_AUTO)
    opened_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'material'],
                condition=models.Q(status='open', origin='auto_min'),
                name='unique_open_auto_shopping',
            ),
        ]


class Alert(TenantModel):
    TYP_LOW = 'low'
    TYP_CRITICAL = 'critical'
    TYP_ZERO = 'zero'
    TYP_SHOPPING = 'shopping'
    STAV_OPEN = 'open'
    STAV_RESOLVED = 'resolved'

    material = models.ForeignKey(Material, related_name='alerts', on_delete=models.CASCADE)
    type = models.CharField(max_length=20)
    status = models.CharField(max_length=20, default=STAV_OPEN, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)


class InboxEvent(models.Model):
    STAV_RECEIVED = 'received'
    STAV_PROCESSED = 'processed'
    STAV_REJECTED = 'rejected'
    STAV_DUPLICATE = 'duplicate'

    event_id = models.CharField(max_length=64, unique=True)
    tenant = models.ForeignKey(Tenant, null=True, blank=True, on_delete=models.SET_NULL)
    source = models.CharField(max_length=40, default='modernik-flow')
    event_type = models.CharField(max_length=80)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=20, default=STAV_RECEIVED)
    reject_reason = models.CharField(max_length=80, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    objects = UnscopedManager()


class AuditLog(models.Model):
    tenant = models.ForeignKey(Tenant, null=True, blank=True, on_delete=models.SET_NULL)
    actor = models.CharField(max_length=80, default='system')
    action = models.CharField(max_length=80)
    request_id = models.CharField(max_length=64, blank=True)
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UnscopedManager()

    class Meta:
        ordering = ['-created_at']
