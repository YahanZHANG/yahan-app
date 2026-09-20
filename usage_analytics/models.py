from django.conf import settings
from django.db import models


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