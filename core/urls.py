from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('scan/', views.scan, name='scan'),
    path('result/', views.result, name='result'),
    path('profile/', views.profile, name='profile'),
    path('history/', views.history, name='history'),
    path('login/', views.login_view, name='login'),
    path("logout/", views.logout_view, name="logout"),
    path('register/', views.register, name='register'),
    path('medicine-details/', views.medicine_details, name='medicine_details'),
    path('risk-assessment/', views.risk_assessment, name='risk_assessment'),
]
