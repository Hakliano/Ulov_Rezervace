from django.contrib import admin

from flow.models import FlowSession, FlowUser


@admin.register(FlowUser)
class FlowUserAdmin(admin.ModelAdmin):
    list_display = ('email', 'salon', 'zamestnanec', 'visible_overview', 'aktivni', 'vytvoreno')
    list_filter = ('aktivni', 'visible_overview', 'salon')
    search_fields = ('email', 'zamestnanec__jmeno')
    readonly_fields = ('password_hash', 'vytvoreno', 'upraveno')


@admin.register(FlowSession)
class FlowSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'token', 'vytvoreno', 'expirace')
    search_fields = ('user__email',)
