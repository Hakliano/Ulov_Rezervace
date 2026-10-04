from django.contrib import admin

from .models import (
    ExtraFaktura,
    HromadnyEmail,
    KamProvize,
    KeyAccountManager,
    PartnerAdminProfil,
    PartnerFeatureGrant,
    PartnerNastaveni,
    PartnerTarif,
    PlatbaPartnera,
    PotencialniKontakt,
    PotencialniSektor,
    TechnickaChyba,
    UlovCisloUctu,
    UpozorneniPlatby,
    Vydaj,
    VydajSablona,
)


@admin.register(PartnerTarif)
class PartnerTarifAdmin(admin.ModelAdmin):
    list_display = ['nazev', 'castka', 'razeni', 'aktivni']
    list_editable = ['castka', 'razeni', 'aktivni']
    ordering = ['razeni', 'id']


@admin.register(PartnerNastaveni)
class PartnerNastaveniAdmin(admin.ModelAdmin):
    list_display = [
        'salon',
        'domena',
        'stav',
        'plan',
        'tarif',
        'povolit_technicke_nastaveni',
        'variabilni_symbol',
        'castka',
        'dalsi_splatnost',
        'kam',
        'prvni_platba',
        'kam_provize',
        'je_testovaci',
    ]
    list_filter = ['stav', 'plan', 'periodicita', 'povolit_technicke_nastaveni', 'je_testovaci', 'kam']
    list_editable = ['povolit_technicke_nastaveni']
    search_fields = ['salon__name', 'domena', 'variabilni_symbol', 'fakturacni_email']

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.plan == obj.PLAN_START:
            from .staff_limits import zajisti_manager_pracuje_pro_start
            try:
                zajisti_manager_pracuje_pro_start(obj.salon)
            except ValueError:
                pass


@admin.register(PlatbaPartnera)
class PlatbaPartneraAdmin(admin.ModelAdmin):
    list_display = ['salon', 'splatnost', 'zaplaceno_dne', 'ocekavana_castka', 'prijata_castka', 'cislo_faktury']
    list_filter = ['zaplaceno_dne']
    search_fields = ['salon__name', 'variabilni_symbol']


@admin.register(UpozorneniPlatby)
class UpozorneniPlatbyAdmin(admin.ModelAdmin):
    list_display = ['salon', 'splatnost', 'prijemce', 'uspesne', 'odeslano']
    list_filter = ['uspesne']
    readonly_fields = [
        'salon', 'splatnost', 'prijemce', 'predmet', 'text',
        'uspesne', 'chyba', 'odeslal', 'odeslano',
    ]


@admin.register(TechnickaChyba)
class TechnickaChybaAdmin(admin.ModelAdmin):
    list_display = ['cas', 'salon', 'typ_chyby', 'cesta', 'vyreseno']
    list_filter = ['vyreseno', 'typ_chyby']
    search_fields = ['salon__name', 'cesta', 'typ_chyby', 'request_id']
    readonly_fields = ['salon', 'request_id', 'cas', 'metoda', 'cesta', 'query', 'status_kod', 'typ_chyby', 'detail', 'stopa']


@admin.register(HromadnyEmail)
class HromadnyEmailAdmin(admin.ModelAdmin):
    list_display = ['vytvoreno', 'predmet', 'okruh', 'odeslano_pocet', 'odeslal']
    readonly_fields = [
        'predmet', 'text', 'okruh', 'tarif',
        'odeslano_pocet', 'preskoceno_pocet', 'chyba_pocet', 'odeslal', 'vytvoreno',
    ]


@admin.register(KeyAccountManager)
class KeyAccountManagerAdmin(admin.ModelAdmin):
    list_display = ['jmeno', 'email', 'telefon', 'cislo_uctu', 'aktivni', 'razeni']
    list_editable = ['aktivni', 'razeni']
    search_fields = ['jmeno', 'email']


@admin.register(KamProvize)
class KamProvizeAdmin(admin.ModelAdmin):
    list_display = ['kam', 'salon', 'typ', 'obdobi', 'castka', 'stav']
    list_filter = ['typ', 'stav', 'obdobi']
    search_fields = ['kam__jmeno', 'salon__name']


@admin.register(UlovCisloUctu)
class UlovCisloUctuAdmin(admin.ModelAdmin):
    list_display = ['cislo', 'popisek', 'primarni', 'aktivni', 'razeni']
    list_editable = ['popisek', 'primarni', 'aktivni', 'razeni']


@admin.register(ExtraFaktura)
class ExtraFakturaAdmin(admin.ModelAdmin):
    list_display = ['cislo_faktury', 'salon', 'castka', 'stav', 'datum_vystaveni']
    list_filter = ['stav']
    search_fields = ['cislo_faktury', 'salon__name', 'variabilni_symbol']


@admin.register(Vydaj)
class VydajAdmin(admin.ModelAdmin):
    list_display = ['datum', 'castka', 'ucet', 'salon', 'poznamka']
    list_filter = ['datum']


@admin.register(VydajSablona)
class VydajSablonaAdmin(admin.ModelAdmin):
    list_display = ['nazev', 'castka', 'ucet']


@admin.register(PotencialniSektor)
class PotencialniSektorAdmin(admin.ModelAdmin):
    list_display = ['nazev', 'razeni']
    list_editable = ['razeni']


@admin.register(PartnerAdminProfil)
class PartnerAdminProfilAdmin(admin.ModelAdmin):
    list_display = ['jmeno', 'user', 'role', 'vytvoreno']
    list_filter = ['role']
    search_fields = ['jmeno', 'user__email', 'user__username']
    raw_id_fields = ['user']


@admin.register(PartnerFeatureGrant)
class PartnerFeatureGrantAdmin(admin.ModelAdmin):
    list_display = [
        'salon',
        'feature',
        'zakaz',
        'aktivni',
        'platnost_od',
        'platnost_do',
        'zdroj',
    ]
    list_filter = ['feature', 'zakaz', 'aktivni', 'zdroj']
    search_fields = ['salon__name', 'feature', 'poznamka']
    raw_id_fields = ['salon']


@admin.register(PotencialniKontakt)
class PotencialniKontaktAdmin(admin.ModelAdmin):
    list_display = ['jmeno', 'email', 'stav', 'sektor', 'telefon', 'web']
    list_filter = ['stav', 'sektor']
    search_fields = ['jmeno', 'email', 'telefon', 'web']
