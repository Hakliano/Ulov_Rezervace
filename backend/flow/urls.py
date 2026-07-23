from django.urls import path

from flow import views

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
]
