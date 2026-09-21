from django.conf import settings
from django.core.validators import MaxLengthValidator
from django.db import models
from django.db.models import F, Q



class ChatMessage(models.Model):

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_sent_messages",
        verbose_name="送信者",
    )

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_received_messages",
        verbose_name="受信者",
    )

    body = models.TextField(
        "メッセージ",
        validators=[
            MaxLengthValidator(2000),
        ],
    )

    is_read = models.BooleanField(
        "既読",
        default=False,
    )

    created_at = models.DateTimeField(
        "送信日時",
        auto_now_add=True,
    )

    class Meta:

        ordering = [
            "created_at",
            "id",
        ]

        verbose_name = "チャットメッセージ"
        verbose_name_plural = "チャットメッセージ"

        indexes = [
            models.Index(
                fields=[
                    "recipient",
                    "is_read",
                    "created_at",
                ],
                name="chat_rec_read_date_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=~Q(
                    sender=F("recipient"),
                ),
                name="chat_no_self_message",
            ),
        ]

    def __str__(self):

        return (
            f"{self.sender} → "
            f"{self.recipient}: "
            f"{self.body[:30]}"
        )

class ChatConnection(models.Model):

    class Status(models.TextChoices):
        PENDING = "pending", "申請中"
        ACCEPTED = "accepted", "友達"
        DECLINED = "declined", "拒否"

    # IDの小さい方
    user_low = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_connections_low",
    )

    # IDの大きい方
    user_high = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_connections_high",
    )

    # 友達申請を送った人
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_friend_requests_sent",
    )

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )

    # ピン留めはユーザーごとに独立
    pinned_low = models.BooleanField(
        default=False,
    )

    pinned_high = models.BooleanField(
        default=False,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:

        constraints = [

            models.UniqueConstraint(
                fields=[
                    "user_low",
                    "user_high",
                ],
                name="unique_chat_pair",
            ),

            models.CheckConstraint(
                condition=Q(
                    user_low_id__lt=F("user_high_id"),
                ),
                name="chat_pair_order",
            ),

        ]

    def __str__(self):

        return (
            f"{self.user_low} / "
            f"{self.user_high} "
            f"({self.status})"
        )

    def other_user(self, user):

        if self.user_low_id == user.pk:
            return self.user_high

        if self.user_high_id == user.pk:
            return self.user_low

        raise ValueError(
            "この友達関係のユーザーではありません。"
        )

    def is_pinned_by(self, user):

        if self.user_low_id == user.pk:
            return self.pinned_low

        if self.user_high_id == user.pk:
            return self.pinned_high

        return False