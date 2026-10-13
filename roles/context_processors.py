from .models import Notification


def notification_summary(request):
    """Unread count + latest few notifications for the header bell."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}
    recent = list(Notification.objects.filter(recipient=user).order_by('-created_at')[:5])
    return {
        'nav_unread_count': Notification.objects.filter(recipient=user, is_read=False).count(),
        'nav_recent_notifications': recent,
    }
