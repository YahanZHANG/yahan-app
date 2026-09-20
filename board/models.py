from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


# =========================================================
# Board post
# =========================================================

class BoardPost(models.Model):

    title = models.CharField(
        "タイトル",
        max_length=150,
    )

    body = models.TextField(
        "本文",
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="board_posts",
        verbose_name="投稿者",
    )

    is_pinned = models.BooleanField(
        "固定のお知らせ",
        default=False,
    )

    created_at = models.DateTimeField(
        "投稿日",
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        "更新日",
        auto_now=True,
    )

    class Meta:

        ordering = [
            "-is_pinned",
            "-created_at",
        ]

        verbose_name = "掲示板の投稿"

        verbose_name_plural = "掲示板の投稿"

    def __str__(self):

        return self.title

    @property
    def is_new(self):

        """
        投稿日から7日以内ならNEWを表示する。
        """

        return (
            self.created_at
            >= timezone.now() - timedelta(days=7)
        )


# =========================================================
# Board comment
# =========================================================

class BoardComment(models.Model):

    post = models.ForeignKey(
        BoardPost,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="投稿",
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="board_comments",
        verbose_name="コメント投稿者",
    )

    body = models.TextField(
        "コメント",
        max_length=1000,
    )

    created_at = models.DateTimeField(
        "投稿日",
        auto_now_add=True,
    )

    class Meta:

        ordering = [
            "created_at",
        ]

        verbose_name = "掲示板のコメント"

        verbose_name_plural = "掲示板のコメント"

    def __str__(self):

        return (
            f"{self.author} - "
            f"{self.post.title}"
        )