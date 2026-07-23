from django.contrib import admin

from .models import PartnerNastaveni, PlatbaPartnera, TechnickaChyba, UpozorneniPlatby


@admin.register(PartnerNastaveni)
class PartnerNastaveniAdmin(admin.ModelAdmin):
    list_display = ['salon', 'domena', 'stav', 'variabilni_symbol', 'castka', 'dalsi_splatnost']
    list_filter = ['stav', 'periodicita']
    search_fields = ['salon__name', 'domena', 'variabilni_symbol', 'fakturacni_email']


@admin.register(PlatbaPartnera)
class PlatbaPartneraAdmin(admin.ModelAdmin):
    list_display = ['salon', 'splatnost', 'zaplaceno_dne', 'ocekavana_castka', 'prijata_castka']
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
    readonly_fields = ['salon', 'request_id', 'cas', 'metoda', 'cesta', 'typ_chyby', 'detail']
