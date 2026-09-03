from django.conf import settings
from django.db import models


class GameScore(models.Model):

    class Game(models.TextChoices):
        BLOCK_BREAKER = (
            "block_breaker",
            "ブロック崩し",
        )

        TAP_STAR = (
            "tap_star",
            "スタータップ",
        )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="game_scores",
    )

    game = models.CharField(
        max_length=30,
        choices=Game.choices,
    )

    # ブロック崩しでは 0
    # スタータップでは 1〜5
    level = models.PositiveSmallIntegerField(
        default=0,
    )

    # 各ユーザーの自己ベストだけ保存する
    score = models.PositiveIntegerField(
        default=0,
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
                    "user",
                    "game",
                    "level",
                ],
                name="unique_game_best_score",
            ),
        ]

        ordering = [
            "-score",
            "updated_at",
        ]

    def __str__(self):
        return (
            f"{self.user} - "
            f"{self.get_game_display()} - "
            f"{self.score}"
        )