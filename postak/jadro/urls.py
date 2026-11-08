from django.urls import path

from . import views

urlpatterns = [
    path('', views.prehled, name='prehled'),
    path('emaily/', views.prazdna, {'klic': 'emaily'}, name='emaily'),
    path('klienti/', views.prazdna, {'klic': 'klienti'}, name='klienti'),
    path('kalendar/', views.prazdna, {'klic': 'kalendar'}, name='kalendar'),
    path('dokumentace/', views.prazdna, {'klic': 'dokumentace'}, name='dokumentace'),
    path('nastaveni/', views.nastaveni, name='nastaveni'),
    path('uzivatele/', views.uzivatele, name='uzivatele'),
    path('uzivatele/novy/', views.uzivatel_novy, name='uzivatel_novy'),
    path('uzivatele/<int:pk>/', views.uzivatel_detail, name='uzivatel_detail'),
    path('prihlaseni/', views.PostakLogin.as_view(), name='prihlaseni'),
    path('odhlaseni/', views.PostakLogout.as_view(), name='odhlaseni'),
]
