"""
URL configuration for salon_api project.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from salon_api.health import health

urlpatterns = [
    path('health/', health, name='health'),
    path('health', health),
    path('admin/', admin.site.urls),
    path('partner-admin/', include('partner_admin.urls')),
    path('api/', include('salons.urls')),
    path('api/', include('rezervace.urls')),
    path('api/', include('flow.urls')),
    path('api/', include('partner_hub.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
