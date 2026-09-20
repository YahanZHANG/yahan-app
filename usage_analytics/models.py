from django.conf import settings
from django.db import models
from django.utils import timezone


class UsageEvent(models.Model):

    class AppKey(models.TextChoices):

        PORTAL = (
            "portal",
            "Portal",
        )

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

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="usage_events",
        verbose_name="ユーザー",
    )

    app_key = models.CharField(
        "アプリ",
        max_length=30,
        choices=AppKey.choices,
    )

    accessed_at = models.DateTimeField(
        "アクセス日時",
        auto_now_add=True,
    )

    is_visit_start = models.BooleanField(
        "新しい訪問",
        default=False,
    )

    class Meta:

        verbose_name = "利用履歴"
        verbose_name_plural = "利用履歴"

        ordering = [
            "-accessed_at",
        ]

        indexes = [

            models.Index(
                fields=[
                    "app_key",
                    "accessed_at",
                ],
            ),

            models.Index(
                fields=[
                    "user",
                    "accessed_at",
                ],
            ),

        ]

    def __str__(self):

        return (
            f"{self.user.username} | "
            f"{self.get_app_key_display()} | "
            f"{self.accessed_at}"
        )

# =========================================================
# Online presence
# =========================================================

class OnlinePresence(models.Model):
    """
    ユーザーのオンライン状態を管理する。

    ブラウザのタブごとに1件保存し、
    Heartbeatを受信するたびに
    last_seenを更新する。

    UsageEventとは独立しているため、
    ページ閲覧数には影響しない。
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="online_presences",
        verbose_name="ユーザー",
    )

    tab_id = models.UUIDField(
        "タブID",
    )

    app_key = models.CharField(
        "利用中のアプリ",
        max_length=30,
        choices=UsageEvent.AppKey.choices,
    )

    last_seen = models.DateTimeField(
        "最終生存確認",
        default=timezone.now,
        db_index=True,
    )

    class Meta:

        verbose_name = "オンライン状態"

        verbose_name_plural = "オンライン状態"

        constraints = [

            models.UniqueConstraint(
                fields=[
                    "user",
                    "tab_id",
                ],
                name="unique_online_presence_per_tab",
            ),

        ]

        indexes = [

            models.Index(
                fields=[
                    "user",
                    "last_seen",
                ],
            ),

        ]

    def __str__(self):

        return (
            f"{self.user.username} | "
            f"{self.get_app_key_display()} | "
            f"{self.last_seen}"
        )