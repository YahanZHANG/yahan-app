from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


# =========================================================
# Board post queryset
# =========================================================

class BoardPostQuerySet(models.QuerySet):

    def visible_to(self, user):

        if not user.is_authenticated:
            return self.none()

        # 管理者はすべて確認できる
        if user.is_superuser:
            return self

        # EXCLUDE投稿のうち、
        # このユーザーが除外対象になっている投稿
        excluded_post_ids = (
            self.filter(
                audience_type="exclude",
                audience_users=user,
            )
            .exclude(
                author=user,
            )
            .values_list(
                "pk",
                flat=True,
            )
        )

        return (
            self.filter(

                # 投稿者自身は必ず見える
                Q(author=user)

                # 全ユーザー向け
                | Q(
                    audience_type="all"
                )

                # 指定ユーザーだけ
                | Q(
                    audience_type="include",
                    audience_users=user,
                )

                # 指定ユーザーを除く
                | Q(
                    audience_type="exclude"
                )

            )
            .exclude(
                pk__in=excluded_post_ids
            )
            .distinct()
        )


# =========================================================
# Board post
# =========================================================

class BoardPost(models.Model):

    class AudienceType(models.TextChoices):

        ALL = (
            "all",
            "全ユーザー",
        )

        INCLUDE = (
            "include",
            "指定したユーザーだけ",
        )

        EXCLUDE = (
            "exclude",
            "指定したユーザーを除く",
        )


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


    # =====================================================
    # Audience
    # =====================================================

    audience_type = models.CharField(
        "公開範囲",
        max_length=20,
        choices=AudienceType.choices,
        default=AudienceType.ALL,
    )

    audience_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="targeted_board_posts",
        verbose_name="対象ユーザー",
    )


    created_at = models.DateTimeField(
        "投稿日",
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        "更新日",
        auto_now=True,
    )


    objects = BoardPostQuerySet.as_manager()


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