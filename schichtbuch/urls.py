from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings

from django.views.static import serve  # expliziter Medien-Serve-View

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('buch.urls')),
]

# Medien IMMER ausliefern – explizite Route auf MEDIA_ROOT
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]