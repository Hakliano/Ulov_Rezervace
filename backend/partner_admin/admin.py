from django.contrib import admin

from .models import (
    HromadnyEmail,
    KamProvize,
    KeyAccountManager,
    PartnerNastaveni,
    PartnerTarif,
    PlatbaPartnera,
    TechnickaChyba,
    UlovCisloUctu,
    UpozorneniPlatby,
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
        'povolit_technicke_nastaveni',
        'variabilni_symbol',
        'castka',
        'dalsi_splatnost',
        'kam',
        'prvni_platba',
        'kam_provize',
        'je_testovaci',
    ]
    list_filter = ['stav', 'periodicita', 'povolit_technicke_nastaveni', 'je_testovaci', 'kam']
    list_editable = ['povolit_technicke_nastaveni']
    search_fields = ['salon__name', 'domena', 'variabilni_symbol', 'fakturacni_email']


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
