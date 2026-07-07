from django.contrib import admin

from rezervace.models import (
    BlokaceCasu,
    OpakovanaRezervace,
    Rezervace,
    RezervaceHistorie,
    RezervacniNastaveni,
    RezervaceSluzba,
    SalonAuditLog,
    SalonVyjimka,
    StatniSvatky,
    Zakaznik,
    Zamestnanec,
    ZamestnanecAbsence,
    ZamestnanecRozvrh,
)


class RezervaceSluzbaInline(admin.TabularInline):
    model = RezervaceSluzba
    extra = 0


@admin.register(Rezervace)
class RezervaceAdmin(admin.ModelAdmin):
    list_display = ['zacatek', 'salon', 'zamestnanec', 'stav', 'kontaktni_jmeno']
    list_filter = ['stav', 'salon']
    inlines = [RezervaceSluzbaInline]


@admin.register(RezervacniNastaveni)
class RezervacniNastaveniAdmin(admin.ModelAdmin):
    list_display = ['salon', 'interval_minut', 'min_predstih_hodin']


class ZamestnanecRozvrhInline(admin.TabularInline):
    model = ZamestnanecRozvrh
    extra = 0


@admin.register(Zamestnanec)
class ZamestnanecAdmin(admin.ModelAdmin):
    list_display = ['jmeno', 'salon', 'specializace', 'aktivni']
    inlines = [ZamestnanecRozvrhInline]


admin.site.register(Zakaznik)
admin.site.register(ZamestnanecAbsence)
admin.site.register(BlokaceCasu)
admin.site.register(SalonVyjimka)
admin.site.register(StatniSvatky)
admin.site.register(RezervaceHistorie)
admin.site.register(SalonAuditLog)
admin.site.register(OpakovanaRezervace)
