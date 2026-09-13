from django.urls import path

from archivnik import views

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
    path('objects/', views.ObjectListCreateView.as_view(), name='archivnik-objects'),
    path(
        'objects/<uuid:object_uuid>/',
        views.ObjectDetailView.as_view(),
        name='archivnik-object-detail',
    ),
    path('entries/', views.EntryListCreateView.as_view(), name='archivnik-entries'),
    path('tags/', views.TagListCreateView.as_view(), name='archivnik-tags'),
    path('reminders/', views.ReminderListCreateView.as_view(), name='archivnik-reminders'),
    path(
        'reminders/<uuid:reminder_uuid>/done/',
        views.ReminderDoneView.as_view(),
        name='archivnik-reminder-done',
    ),
]
