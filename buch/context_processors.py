from django.contrib.auth.models import AnonymousUser
from .models import MentionNotification


def mention_notification_badge(request):
    """
    Liefert die Anzahl ungelesener @-Mention-Benachrichtigungen
    für den aktuell angemeldeten Benutzer, damit sie im Header
    als Badge angezeigt werden kann.
    """
    user = getattr(request, "user", None)

    if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
        return {"header_unread_notifications_count": 0}

    count = MentionNotification.objects.filter(
        user=user,
        is_read=False,
    ).count()

    return {"header_unread_notifications_count": count}