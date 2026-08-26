from django.contrib import admin
from django.urls import include, path

from sklad.health import health

urlpatterns = [
    path('health/', health),
    path('admin/', admin.site.urls),
    path('', include('sklad.urls')),
]
