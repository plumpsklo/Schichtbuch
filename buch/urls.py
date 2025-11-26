from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('eintrag/neu/', views.new_entry, name='new_entry'),
    path('eintrag/<int:entry_id>/', views.entry_detail, name='entry_detail'),
    path('debug-media/', views.debug_media, name='debug_media'),

    path('login/', auth_views.LoginView.as_view(template_name='buch/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]