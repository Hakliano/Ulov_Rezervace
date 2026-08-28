from django.urls import path

from flow import mail_views, owner_views, provoz_views, views
from flow import customer_card_views
from flow import materialnik_views as views_materialnik
from flow import integrations_views

urlpatterns = [
    path(
        'integrations/v1/materialnik/session',
        integrations_views.MaterialnikSessionView.as_view(),
        name='integrations-materialnik-session',
    ),
    path(
        'integrations/v1/materialnik/catalog',
        integrations_views.MaterialnikCatalogView.as_view(),
        name='integrations-materialnik-catalog',
    ),
    path('salon/<int:pk>/flow/aktivace/', views.FlowAktivaceView.as_view(), name='flow-aktivace'),
    path(
        'salon/<int:pk>/flow/majitelka-pracuje/',
        views.MajitelkaPracujeView.as_view(),
        name='flow-majitelka-pracuje',
    ),
    path('salon/<int:pk>/flow/ucty/', views.FlowUctyListCreateView.as_view(), name='flow-ucty'),
    path(
        'salon/<int:pk>/flow/ucty/<int:ucet_id>/',
        views.FlowUcetDetailView.as_view(),
        name='flow-ucet-detail',
    ),
    path(
        'salon/<int:pk>/flow/ucty/<int:ucet_id>/reset-hesla/',
        views.FlowUcetResetHeslaView.as_view(),
        name='flow-ucet-reset',
    ),
    path(
        'salon/<int:pk>/flow/zamestnanci/<int:zamestnanec_id>/',
        views.FlowUcetProZamestnanceView.as_view(),
        name='flow-zamestnanec',
    ),
    path('flow/prihlaseni/', views.FlowPrihlaseniView.as_view(), name='flow-prihlaseni'),
    path('flow/odhlaseni/', views.FlowOdhlaseniView.as_view(), name='flow-odhlaseni'),
    path('flow/me/', views.FlowMeView.as_view(), name='flow-me'),
    path('flow/prepnout-personu/', views.FlowPrepnoutPersonuView.as_view(), name='flow-prepnout-personu'),
    path('flow/zmena-hesla/', views.FlowZmenaHeslaView.as_view(), name='flow-zmena-hesla'),
    path('flow/owner/nastaveni/', owner_views.FlowOwnerNastaveniView.as_view(), name='flow-owner-nastaveni'),
    path(
        'flow/owner/pracovni-persona/',
        owner_views.FlowOwnerPracovniPersonaView.as_view(),
        name='flow-owner-pracovni-persona',
    ),
    path('flow/owner/personal/', owner_views.FlowOwnerPersonalListCreateView.as_view(), name='flow-owner-personal'),
    path(
        'flow/owner/personal/<int:zamestnanec_id>/',
        owner_views.FlowOwnerPersonalDetailView.as_view(),
        name='flow-owner-personal-detail',
    ),
    path(
        'flow/owner/personal/<int:zamestnanec_id>/flow/',
        owner_views.FlowOwnerPersonalFlowCreateView.as_view(),
        name='flow-owner-personal-flow-create',
    ),
    path(
        'flow/owner/personal/<int:zamestnanec_id>/flow/patch/',
        owner_views.FlowOwnerPersonalFlowPatchView.as_view(),
        name='flow-owner-personal-flow-patch',
    ),
    path(
        'flow/owner/personal/<int:zamestnanec_id>/flow/reset-hesla/',
        owner_views.FlowOwnerPersonalFlowResetView.as_view(),
        name='flow-owner-personal-flow-reset',
    ),
    path('flow/owner/absence/', owner_views.FlowOwnerAbsenceListView.as_view(), name='flow-owner-absence'),
    path(
        'flow/owner/absence/<int:absence_id>/schvalit/',
        owner_views.FlowOwnerAbsenceSchvalitView.as_view(),
        name='flow-owner-absence-schvalit',
    ),
    path(
        'flow/owner/absence/<int:absence_id>/zamitnout/',
        owner_views.FlowOwnerAbsenceZamitnoutView.as_view(),
        name='flow-owner-absence-zamitnout',
    ),
    path(
        'flow/owner/absence/<int:absence_id>/',
        owner_views.FlowOwnerAbsenceDeleteView.as_view(),
        name='flow-owner-absence-delete',
    ),
    path('flow/owner/platby/', owner_views.FlowOwnerPlatbyView.as_view(), name='flow-owner-platby'),
    path(
        'flow/owner/platby/<int:platba_id>/faktura/',
        owner_views.FlowOwnerPlatbaFakturaView.as_view(),
        name='flow-owner-platba-faktura',
    ),
    path(
        'flow/owner/extra-faktury/<int:faktura_id>/faktura/',
        owner_views.FlowOwnerExtraFakturaView.as_view(),
        name='flow-owner-extra-faktura',
    ),
    path('flow/owner/audit-log/', owner_views.FlowOwnerAuditLogView.as_view(), name='flow-owner-audit'),
    path('flow/owner/no-show-archiv/', owner_views.FlowOwnerNoShowArchivView.as_view(), name='flow-owner-noshow'),
    path(
        'flow/owner/no-show-blokovat/',
        owner_views.FlowOwnerNoShowBlokovatView.as_view(),
        name='flow-owner-noshow-blok',
    ),
    path(
        'flow/owner/no-show-odblokovat/',
        owner_views.FlowOwnerNoShowOdblokovatView.as_view(),
        name='flow-owner-noshow-odblok',
    ),
    path('flow/owner/statistiky/', owner_views.FlowOwnerStatistikyView.as_view(), name='flow-owner-statistiky'),
    path(
        'flow/owner/prirazeni-sluzeb/',
        owner_views.FlowOwnerPrirazeniSluzebView.as_view(),
        name='flow-owner-prirazeni-sluzeb',
    ),
    path('flow/kalendar/', provoz_views.FlowKalendarView.as_view(), name='flow-kalendar'),
    path(
        'flow/rezervace/<int:rezervace_id>/dokonceno/',
        provoz_views.FlowRezervaceDokoncenoView.as_view(),
        name='flow-rezervace-dokonceno',
    ),
    path(
        'flow/rezervace/<int:rezervace_id>/materialnik-spotreba/',
        views_materialnik.FlowMaterialnikSpotrebaView.as_view(),
        name='flow-rezervace-materialnik-spotreba',
    ),
    path(
        'flow/materialnik-prehled/',
        views_materialnik.FlowMaterialnikPrehledView.as_view(),
        name='flow-materialnik-prehled',
    ),
    path(
        'flow/rezervace/<int:rezervace_id>/noshow/',
        provoz_views.FlowRezervaceNoShowView.as_view(),
        name='flow-rezervace-noshow',
    ),
    path(
        'flow/rezervace/<int:rezervace_id>/storno/',
        provoz_views.FlowRezervaceStornoView.as_view(),
        name='flow-rezervace-storno',
    ),
    path(
        'flow/rezervace/<int:rezervace_id>/prevest/',
        provoz_views.FlowRezervacePrevestView.as_view(),
        name='flow-rezervace-prevest',
    ),
    path(
        'flow/rezervace/<int:rezervace_id>/platba/',
        provoz_views.FlowRezervacePlatbaView.as_view(),
        name='flow-rezervace-platba',
    ),
    path(
        'flow/rezervace/<int:rezervace_id>/zaloha-ok/',
        provoz_views.FlowRezervaceZalohaOkView.as_view(),
        name='flow-rezervace-zaloha-ok',
    ),
    path(
        'flow/rezervace/<int:rezervace_id>/zaloha-nepozadovat/',
        provoz_views.FlowRezervaceZalohaNepozadovatView.as_view(),
        name='flow-rezervace-zaloha-nepozadovat',
    ),
    path(
        'flow/rezervace/<int:rezervace_id>/email-preview/',
        provoz_views.FlowEmailPreviewView.as_view(),
        name='flow-rezervace-email-preview',
    ),
    path('flow/absence/', provoz_views.FlowAbsenceView.as_view(), name='flow-absence'),
    path(
        'flow/absence/<int:absence_id>/',
        provoz_views.FlowAbsenceDetailView.as_view(),
        name='flow-absence-detail',
    ),
    path('flow/rozvrh/', provoz_views.FlowRozvrhView.as_view(), name='flow-rozvrh'),
    path('flow/sluzby/', provoz_views.FlowSluzbyView.as_view(), name='flow-sluzby'),
    path('flow/volne-terminy/', provoz_views.FlowVolneTerminyView.as_view(), name='flow-volne-terminy'),
    path('flow/rezervace/', provoz_views.FlowRezervaceCreateView.as_view(), name='flow-rezervace-create'),
    path('flow/mail/stav/', mail_views.FlowMailStavView.as_view(), name='flow-mail-stav'),
    path('flow/mail/odeslat/', mail_views.FlowMailOdeslatView.as_view(), name='flow-mail-odeslat'),
    path('flow/mail/odeslane/', mail_views.FlowMailOdeslaneListView.as_view(), name='flow-mail-odeslane'),
    path(
        'flow/mail/odeslane/<int:pk>/',
        mail_views.FlowMailOdeslaneDetailView.as_view(),
        name='flow-mail-odeslane-detail',
    ),
    path('flow/mail/', mail_views.FlowMailListView.as_view(), name='flow-mail-list'),
    path('flow/mail/<int:uid>/', mail_views.FlowMailDetailView.as_view(), name='flow-mail-detail'),
    # --- Karta zákazníka (feature/flow-customer-card) ---
    path(
        'flow/zakaznicke-karty/',
        customer_card_views.CustomerCardListCreateView.as_view(),
        name='flow-customer-cards',
    ),
    path(
        'flow/zakaznicke-karty/lookup/',
        customer_card_views.CustomerCardLookupView.as_view(),
        name='flow-customer-card-lookup',
    ),
    path(
        'flow/zakaznicke-karty/<int:card_id>/',
        customer_card_views.CustomerCardDetailView.as_view(),
        name='flow-customer-card-detail',
    ),
    path(
        'flow/zakaznicke-karty/<int:card_id>/odeslat-potvrzeni/',
        customer_card_views.CustomerCardSendConfirmView.as_view(),
        name='flow-customer-card-send-confirm',
    ),
    path(
        'flow/zakaznicke-karty/<int:card_id>/aktivovat-lokalne/',
        customer_card_views.CustomerCardActivateLocalView.as_view(),
        name='flow-customer-card-activate-local',
    ),
    path(
        'flow/zakaznicke-karty/<int:card_id>/navstevy/',
        customer_card_views.CustomerCardVisitCreateView.as_view(),
        name='flow-customer-card-visits',
    ),
    path(
        'flow/zakaznicka-karta/potvrdit/<str:token>/',
        customer_card_views.CustomerCardConfirmPublicView.as_view(),
        name='flow-customer-card-confirm',
    ),
]
