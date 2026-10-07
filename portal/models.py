from django.conf import settings
from django.db import models


class PortalAppPreference(models.Model):
    """
    Portalに表示するアプリと、
    ユーザーごとの表示順を保存する。
    """

    class AppKey(models.TextChoices):

        NEWS = (
            "news",
            "スイスニュース",
        )

        FEEDING = (
            "feeding",
            "子育て（離乳食記録）",
        )

        VACCINATION = (
            "vaccination",
            "子育て（ワクチン記録）",
        )

        RECIPES = (
            "recipes",
            "料理・レシピ",
        )

        GAMES = (
            "games",
            "ミニゲーム",
        )

        COLORCHECK = (
            "colorcheck",
            "色判定",
        )

        EVENTS = (
            "events",
            "イベント・日程調整",
        )

        CHAT = (
            "chat",
            "チャット",
        )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ユーザー",
        on_delete=models.CASCADE,
        related_name="portal_app_preferences",
    )

    app_key = models.CharField(
        "アプリ",
        max_length=30,
        choices=AppKey.choices,
    )

    is_visible = models.BooleanField(
        "Portalに表示する",
        default=True,
    )

    display_order = models.PositiveIntegerField(
        "表示順",
        default=0,
    )

    created_at = models.DateTimeField(
        "作成日時",
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        "更新日時",
        auto_now=True,
    )

    class Meta:
        verbose_name = "Portalアプリ設定"
        verbose_name_plural = "Portalアプリ設定"

        ordering = [
            "display_order",
            "id",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "user",
                    "app_key",
                ],
                name="unique_portal_app_preference_per_user",
            ),
        ]

    def __str__(self):
        return (
            f"{self.user.username} - "
            f"{self.get_app_key_display()}"
        )


class AppAccessRequest(models.Model):

    class AppKey(models.TextChoices):

        FEEDING = (
            "feeding",
            "離乳食記録",
        )

        VACCINATION = (
            "vaccination",
            "ワクチン記録",
        )

        GAMES = (
            "games",
            "ミニゲーム",
        )

        CHAT = (
            "chat",
            "チャット",
        )

        BOARD = (
            "board",
            "掲示板",
        )


    class Status(models.TextChoices):

        PENDING = (
            "pending",
            "確認待ち",
        )

        APPROVED = (
            "approved",
            "承認",
        )

        DECLINED = (
            "declined",
            "見送り",
        )


    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="app_access_requests",
    )

    app_key = models.CharField(
        "利用希望アプリ",
        max_length=30,
        choices=AppKey.choices,
    )

    status = models.CharField(
        "ステータス",
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    requested_path = models.CharField(
        "申請元URL",
        max_length=500,
        blank=True,
    )

    created_at = models.DateTimeField(
        "申請日時",
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        "更新日時",
        auto_now=True,
    )


    class Meta:

        ordering = [
            "-created_at",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "user",
                    "app_key",
                ],
                name="unique_app_access_request_per_user",
            ),
        ]


    def __str__(self):

        return (
            f"{self.user.username} - "
            f"{self.get_app_key_display()}"
        )