import logging

from django.conf import settings
from django.core.mail import send_mail


logger = logging.getLogger(__name__)


def send_admin_alert(subject, message):
    """Email the admin about an Outings problem; no-op without ADMIN_NOTIFICATION_EMAIL."""
    recipient = getattr(settings, "ADMIN_NOTIFICATION_EMAIL", "")
    if not recipient:
        logger.warning("ADMIN_NOTIFICATION_EMAIL is not set: %s", subject)
        return False
    try:
        send_mail(
            subject=f"[Yapp おでかけ] {subject}",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
        )
    except Exception:
        logger.exception("Failed to send admin alert: %s", subject)
        return False
    return True
