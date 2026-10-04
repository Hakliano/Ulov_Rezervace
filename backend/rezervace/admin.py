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
    ZamestnanecSluzba,
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
    exclude = ['smtp_password']


class ZamestnanecRozvrhInline(admin.TabularInline):
    model = ZamestnanecRozvrh
    extra = 0


class ZamestnanecSluzbaInline(admin.TabularInline):
    model = ZamestnanecSluzba
    extra = 0


@admin.register(Zamestnanec)
class ZamestnanecAdmin(admin.ModelAdmin):
    list_display = ['jmeno', 'salon', 'specializace', 'aktivni']
    inlines = [ZamestnanecRozvrhInline, ZamestnanecSluzbaInline]

    def save_model(self, request, obj, form, change):
        from partner_admin.staff_limits import ExtraStaffNeniVNaroku, over_reaktivaci_extra_staff, over_vytvoreni_extra_staff

        if obj.role == Zamestnanec.ROLE_ZAMESTNANEC and obj.aktivni:
            try:
                if not change:
                    over_vytvoreni_extra_staff(obj.salon)
                elif 'aktivni' in form.changed_data:
                    over_reaktivaci_extra_staff(obj.salon, obj)
            except ExtraStaffNeniVNaroku as exc:
                from django.core.exceptions import ValidationError
                raise ValidationError(str(exc)) from exc
        super().save_model(request, obj, form, change)


admin.site.register(Zakaznik)
admin.site.register(ZamestnanecAbsence)
admin.site.register(BlokaceCasu)
admin.site.register(SalonVyjimka)
admin.site.register(StatniSvatky)
admin.site.register(RezervaceHistorie)
admin.site.register(SalonAuditLog)
admin.site.register(OpakovanaRezervace)
