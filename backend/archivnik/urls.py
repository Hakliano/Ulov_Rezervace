from django.urls import path

from archivnik import views
from archivnik import views_evidence

urlpatterns = [
    path('auth/login/', views.LoginView.as_view(), name='archivnik-login'),
    path('auth/logout/', views.LogoutView.as_view(), name='archivnik-logout'),
    path('me/', views.MeView.as_view(), name='archivnik-me'),
    path('overview/', views.OverviewView.as_view(), name='archivnik-overview'),
    path('search/', views.SearchView.as_view(), name='archivnik-search'),
    path('customers/', views.CustomerListCreateView.as_view(), name='archivnik-customers'),
    path(
        'customers/<uuid:customer_uuid>/',
        views.CustomerDetailView.as_view(),
        name='archivnik-customer-detail',
    ),
    path('object-types/', views.ObjectTypeListCreateView.as_view(), name='archivnik-object-types'),
    path('obory/', views.OborListCreateView.as_view(), name='archivnik-obory'),
    path('presets/', views.PresetListView.as_view(), name='archivnik-presets'),
    path('presets/apply/', views.PresetApplyView.as_view(), name='archivnik-presets-apply'),
    path('fields/', views_evidence.FieldListCreateView.as_view(), name='archivnik-fields'),
    path('objects/', views.ObjectListCreateView.as_view(), name='archivnik-objects'),
    path(
        'objects/<uuid:object_uuid>/',
        views.ObjectDetailView.as_view(),
        name='archivnik-object-detail',
    ),
    path(
        'objects/<uuid:object_uuid>/fields/',
        views_evidence.ObjectFieldValuesView.as_view(),
        name='archivnik-object-fields',
    ),
    path(
        'objects/<uuid:object_uuid>/cover/',
        views_evidence.ObjectCoverView.as_view(),
        name='archivnik-object-cover',
    ),
    path('entries/', views.EntryListCreateView.as_view(), name='archivnik-entries'),
    path('tags/', views.TagListCreateView.as_view(), name='archivnik-tags'),
    path('reminders/', views.ReminderListCreateView.as_view(), name='archivnik-reminders'),
    path(
        'reminders/<uuid:reminder_uuid>/done/',
        views.ReminderDoneView.as_view(),
        name='archivnik-reminder-done',
    ),
    path('assets/', views_evidence.AssetListCreateView.as_view(), name='archivnik-assets'),
    path(
        'assets/<uuid:asset_uuid>/content/',
        views_evidence.AssetContentView.as_view(),
        name='archivnik-asset-content',
    ),
    path(
        'assets/<uuid:asset_uuid>/',
        views_evidence.AssetDetailView.as_view(),
        name='archivnik-asset-detail',
    ),
]
