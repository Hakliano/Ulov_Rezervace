from django.urls import path

from . import internal_views, views

app_name = 'sklad'

urlpatterns = [
    path('v1/internal/tenants', internal_views.provision_tenant),
    path('v1/internal/tenants/<uuid:tenant_uuid>/deactivate', internal_views.deactivate_tenant),
    path('v1/internal/consume-preview', internal_views.consume_preview),
    path('v1/internal/consume', internal_views.consume_confirm),
    path('v1/events', internal_views.ingest_event),
    path('prihlaseni/', views.login_view, name='login'),
    path('odhlaseni/', views.logout_view, name='logout'),
    path('', views.home, name='home'),
    path('materialy/', views.materials, name='materials'),
    path('materialy/novy/', views.material_form, name='material_new'),
    path('materialy/<int:pk>/', views.material_form, name='material_edit'),
    path('dodavatele/', views.suppliers, name='suppliers'),
    path('spotreba/', views.consume, name='consume'),
    path('inventura/', views.inventory, name='inventory'),
    path('nakup/', views.shopping, name='shopping'),
    path('historie/', views.movements, name='movements'),
    path('receptury/', views.recipes, name='recipes'),
    path('receptury/nova/', views.recipe_form, name='recipe_new'),
    path('receptury/<int:pk>/', views.recipe_form, name='recipe_edit'),
    path('upozorneni/', views.alerts, name='alerts'),
    path('kategorie/', views.categories, name='categories'),
    path('jednotky/', views.units, name='units'),
    path('prehledy/', views.reports, name='reports'),
]
