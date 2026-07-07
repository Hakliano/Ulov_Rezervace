from django.contrib import admin

from .models import CenikPolozka, Novinka, OteviraciDoba, Salon, SalonObrazek


class CenikInline(admin.TabularInline):
    model = CenikPolozka
    extra = 1


class NovinkaInline(admin.StackedInline):
    model = Novinka
    extra = 1
    fields = ['nadpis', 'text', 'obrazek']


class OteviraciDobaInline(admin.TabularInline):
    model = OteviraciDoba
    extra = 0
    max_num = 7


class ObrazekInline(admin.TabularInline):
    model = SalonObrazek
    extra = 1
    fields = ['url', 'popis', 'poradi']


@admin.register(Salon)
class SalonAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'phone', 'email']
    fields = ['name', 'description', 'address', 'phone', 'email', 'hero_image']
    inlines = [CenikInline, NovinkaInline, OteviraciDobaInline, ObrazekInline]
