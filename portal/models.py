from django.conf import settings
from django.db import models


class PortalAppPreference(models.Model):
    """
    Portalに表示するアプリと、
    ユーザーごとの表示順を保存する。
    """

    class AppKey(models.TextChoices):
        NEWS = "news", "スイスニュース"
        FEEDING = "feeding", "子育て（離乳食記録）"
        VACCINATION = "vaccination", "子育て（ワクチン記録）"
        RECIPES = "recipes", "料理・レシピ"
        GAMES = "games", "ミニゲーム"
        COLORCHECK = "colorcheck", "色判定"

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