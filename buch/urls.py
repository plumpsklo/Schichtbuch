from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Startseite / Übersicht
    path('', views.home, name='home'),

    # Neuer Eintrag
    path('eintrag/neu/', views.new_entry, name='new_entry'),

    #Makieren von Usern in Einträgen
    path("mentions/", views.mention_notifications_view, name="mention_notifications"),

    # Detailansicht eines Eintrags
    path('eintrag/<int:entry_id>/', views.entry_detail, name='entry_detail'),

    # 🔧 Eintrag ergänzen / bearbeiten
    path('eintrag/<int:entry_id>/update/', views.update_entry, name='update_entry'),

        # SAP-Bearbeitungsstatus für Ersatzteile toggeln (nur Meister/Admin)
    path(
        'eintrag/<int:entry_id>/spares-toggle/',
        views.toggle_spare_parts_processed,
        name='toggle_spare_parts_processed',
    ),

    # Hinweise / Erwähnungen
    path("notifications/", views.notifications_inbox, name="notifications_inbox"),
    
    # Debug-Seite für Medien
    path('debug-media/', views.debug_media, name='debug_media'),

    # Like / Unlike
    path('eintrag/<int:entry_id>/like/', views.toggle_like, name='toggle_like'),

    # 🔐 Login / Logout
    path(
        'login/',
        auth_views.LoginView.as_view(template_name='buch/login.html'),
        name='login'
    ),
    path(
        'logout/',
        auth_views.LogoutView.as_view(),
        name='logout'
    ),

    # 🔐 Passwort ändern
    path(
        'passwort-aendern/',
        auth_views.PasswordChangeView.as_view(
            template_name='buch/password_change.html',
            success_url='/passwort-aendern/erfolg/'
        ),
        name='password_change'
    ),
    path(
        'passwort-aendern/erfolg/',
        auth_views.PasswordChangeDoneView.as_view(
            template_name='buch/password_change_done.html'
        ),
        name='password_change_done'
    ),
]