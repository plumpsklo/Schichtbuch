from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('buch.urls')),
]

# Medien IMMER ausliefern (auch bei DEBUG=False, z. B. auf Render)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)