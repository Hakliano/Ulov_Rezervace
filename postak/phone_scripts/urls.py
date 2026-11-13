from django.urls import path

from . import manage_views, views

urlpatterns = [
    path('', views.priprava, name='telefonni_klikacka'),
    path(
        'api/snapshot-version/<int:version_id>/',
        views.snapshot_api_version,
        name='telefonni_klikacka_snapshot_version',
    ),
    path(
        'api/snapshot/<slug:slug>/',
        views.snapshot_api,
        name='telefonni_klikacka_snapshot',
    ),
    path('sprava/', manage_views.sprava_seznam, name='telefonni_klikacka_sprava_seznam'),
    path('sprava/novy/', manage_views.sprava_novy, name='telefonni_klikacka_sprava_novy'),
    path('sprava/import/', manage_views.sprava_import, name='telefonni_klikacka_sprava_import'),
    path('sprava/import/<slug:slug>/', manage_views.sprava_import, name='telefonni_klikacka_sprava_import_script'),
    path('sprava/<slug:slug>/verze/', manage_views.sprava_verze, name='telefonni_klikacka_sprava_verze'),
    path(
        'sprava/<slug:slug>/deaktivovat/',
        manage_views.sprava_deaktivovat,
        name='telefonni_klikacka_sprava_deaktivovat',
    ),
    path(
        'sprava/verze/<int:version_id>/export/',
        manage_views.sprava_export,
        name='telefonni_klikacka_sprava_export',
    ),
    path(
        'sprava/verze/<int:version_id>/publikovat/',
        manage_views.sprava_publikovat,
        name='telefonni_klikacka_sprava_publikovat',
    ),
    path(
        'sprava/verze/<int:version_id>/testovat/',
        manage_views.sprava_testovat,
        name='telefonni_klikacka_sprava_testovat',
    ),
]
