from django.urls import path

from partner_hub import views

urlpatterns = [
    path('partner/prihlaseni/', views.PartnerPrihlaseniView.as_view()),
    path('partner/me/', views.PartnerMeView.as_view()),
    path('partner/salony/', views.PartnerSalonyView.as_view()),
    path('partner/salony/<int:pk>/', views.PartnerSalonDetailView.as_view()),
]
