from .models import SwissBoardNotification


def notification_count(request):

    if not request.user.is_authenticated:
        return {
            "sb_unread_count": 0,
        }

    count = SwissBoardNotification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).count()

    return {
        "sb_unread_count": count,
    }