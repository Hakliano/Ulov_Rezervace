from django.urls import path

from . import views


app_name = 'partner_admin'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('export.csv', views.export_csv, name='export_csv'),
    path('salon/<int:salon_id>/', views.detail_partnera, name='detail'),
    path('salon/<int:salon_id>/platby.csv', views.export_platby_csv, name='export_platby_csv'),
    path('salon/<int:salon_id>/nastaveni/', views.ulozit_nastaveni, name='ulozit_nastaveni'),
    path('salon/<int:salon_id>/blokovat/', views.blokovat, name='blokovat'),
    path('salon/<int:salon_id>/aktivovat/', views.aktivovat, name='aktivovat'),
    path('salon/<int:salon_id>/platba/', views.potvrdit_platbu, name='potvrdit_platbu'),
    path('salon/<int:salon_id>/upozorneni/', views.odeslat_upozorneni, name='odeslat_upozorneni'),
    path(
        'salon/<int:salon_id>/ucet/<int:zamestnanec_id>/reset/',
        views.reset_hesla,
        name='reset_hesla',
    ),
    path('chyba/<int:chyba_id>/vyresit/', views.vyresit_chybu, name='vyresit_chybu'),
]
