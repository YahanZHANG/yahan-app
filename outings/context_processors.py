
from .models import OutingsNotification


def outings_notifications(request):

    if not request.path.startswith("/outings/"):
        return {}

    if not request.user.is_authenticated:
        return {
            "outings_unread_count": 0,
        }

    count = OutingsNotification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).count()

    return {
        "outings_unread_count": count,
    }
