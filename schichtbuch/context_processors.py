from django.conf import settings

def app_version(request):
    return {
        'APP_VERSION': getattr(settings, 'APP_VERSION', '0.2'),
        'APP_STAGE': getattr(settings, 'APP_STAGE', ''),
    }