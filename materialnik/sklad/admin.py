from django.contrib import admin

from .models import Material, Tenant, Unit


admin.site.register(Tenant)
admin.site.register(Unit)
admin.site.register(Material)
