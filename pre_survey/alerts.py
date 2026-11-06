"""
利用者が質問を追加したら、管理者にメールで知らせる (おかしな質問にすぐ気づけるように)。
送り先は和食アプリと同じ ADMIN_NOTIFICATION_EMAIL。なければ何もしない。
"""

import logging
import threading

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse


logger = logging.getLogger(__name__)


def _send(subject, message, recipient):
    try:
        send_mail(
            subject=f"[Yapp 事前アンケート] {subject}",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
        )
    except Exception:
        logger.exception("Failed to send pre-survey alert: %s", subject)


def notify_new_question(request, question):
    recipient = getattr(settings, "ADMIN_NOTIFICATION_EMAIL", "")

    if not recipient:
        logger.warning("ADMIN_NOTIFICATION_EMAIL is not set: new pre-survey question %s", question.pk)
        return False

    admin_url = request.build_absolute_uri(reverse("admin:pre_survey_question_change", args=[question.pk]))
    message = (
        f"利用者が質問を追加しました（すぐ公開されています）。\n\n"
        f"質問: {question.body}\n"
        f"テーマ: {question.get_theme_display()}\n"
        f"投稿者: {question.display_name}"
        f"{f' ({question.user.username})' if question.user else ''}\n\n"
        f"おかしな質問なら、管理画面で非公開・却下にしてください。\n{admin_url}\n"
    )
    subject = f"新しい質問: {question.body[:30]}"

    # メールの送信で、質問を追加した人を待たせない
    threading.Thread(target=_send, args=(subject, message, recipient), daemon=True).start()
    return True
