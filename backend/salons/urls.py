from django.urls import path

from .views import (
    AuthLoginView,
    BunnyStatusView,
    ImageDeleteView,
    ImageUploadView,
    PoptavkaView,
    SalonDetailView,
    SalonKontaktView,
)

urlpatterns = [
    path('auth/login/', AuthLoginView.as_view(), name='auth-login'),
    path('poptavka/', PoptavkaView.as_view(), name='poptavka'),
    path('bunny/status/', BunnyStatusView.as_view(), name='bunny-status'),
    path('salon/<int:pk>/', SalonDetailView.as_view(), name='salon-detail'),
    path('salon/<int:pk>/kontakt/', SalonKontaktView.as_view(), name='salon-kontakt'),
    path('salon/<int:pk>/upload/', ImageUploadView.as_view(), name='salon-upload'),
    path('salon/<int:pk>/obrazek/<int:image_id>/', ImageDeleteView.as_view(), name='salon-obrazek-delete'),
]
