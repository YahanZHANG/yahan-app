import logging

from django.conf import settings
from django.core.mail import send_mail


logger = logging.getLogger(__name__)


def send_admin_alert(subject, message):
    """
    管理者にメールで知らせる。ADMIN_NOTIFICATION_EMAIL がなければ何もしない。
    """

    recipient = getattr(settings, "ADMIN_NOTIFICATION_EMAIL", "")

    if not recipient:
        logger.warning("ADMIN_NOTIFICATION_EMAIL is not set: %s", subject)
        return False

    try:
        send_mail(
            subject=f"[Yapp スイスで和食] {subject}",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
        )
    except Exception:
        logger.exception("Failed to send admin alert: %s", subject)
        return False

    return True
