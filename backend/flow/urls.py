from django.urls import path

from flow import mail_views, provoz_views, views

urlpatterns = [
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
    path('flow/zmena-hesla/', views.FlowZmenaHeslaView.as_view(), name='flow-zmena-hesla'),
    path('flow/kalendar/', provoz_views.FlowKalendarView.as_view(), name='flow-kalendar'),
    path(
        'flow/rezervace/<int:rezervace_id>/dokonceno/',
        provoz_views.FlowRezervaceDokoncenoView.as_view(),
        name='flow-rezervace-dokonceno',
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
]
