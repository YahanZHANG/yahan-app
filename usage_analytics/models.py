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

# =========================================================
# Public News Analytics
# =========================================================

class PublicNewsEvent(models.Model):
    """
    ログインしていない公開Yahan News閲覧者の
    匿名アクセス履歴。

    visitor_id はブラウザ単位のランダムIDで、
    個人を特定する情報は保存しない。
    """

    visitor_id = models.UUIDField(
        "匿名訪問者ID",
        db_index=True,
    )

    path = models.CharField(
        "閲覧ページ",
        max_length=500,
        blank=True,
    )

    accessed_at = models.DateTimeField(
        "アクセス日時",
        auto_now_add=True,
        db_index=True,
    )

    is_visit_start = models.BooleanField(
        "新しい訪問",
        default=False,
    )

    class Meta:

        verbose_name = "公開ニュース利用履歴"
        verbose_name_plural = "公開ニュース利用履歴"

        ordering = [
            "-accessed_at",
        ]

        indexes = [

            models.Index(
                fields=[
                    "visitor_id",
                    "accessed_at",
                ],
            ),

        ]

    def __str__(self):

        return (
            f"{self.visitor_id} | "
            f"{self.path} | "
            f"{self.accessed_at}"
        )


# =========================================================
# Public News Article Click Analytics
# =========================================================

class PublicNewsArticleClick(models.Model):
    """
    ログインしていない公開Swiss News閲覧者が
    元記事へのリンクをクリックした履歴。

    PublicNewsEventとは分離し、
    ページ閲覧数には含めない。
    """

    visitor_id = models.UUIDField(
        "匿名訪問者ID",
        db_index=True,
    )

    article_id = models.PositiveBigIntegerField(
        "記事ID",
        db_index=True,
    )

    article_title = models.CharField(
        "記事タイトル",
        max_length=500,
    )

    source_name = models.CharField(
        "ニュースソース",
        max_length=200,
        blank=True,
    )

    destination_url = models.URLField(
        "リンク先",
        max_length=2000,
    )

    clicked_at = models.DateTimeField(
        "クリック日時",
        auto_now_add=True,
        db_index=True,
    )

    class Meta:

        verbose_name = "公開ニュース記事クリック"
        verbose_name_plural = "公開ニュース記事クリック"

        ordering = [
            "-clicked_at",
        ]

        indexes = [

            models.Index(
                fields=[
                    "visitor_id",
                    "clicked_at",
                ],
            ),

            models.Index(
                fields=[
                    "article_id",
                    "clicked_at",
                ],
            ),

        ]

    def __str__(self):

        return (
            f"{self.visitor_id} | "
            f"{self.article_title} | "
            f"{self.clicked_at}"
        )

# =========================================================
# Authenticated News Page Analytics
# =========================================================

class UserNewsEvent(models.Model):
    """
    ログインユーザーのSwiss News内での
    ページ閲覧履歴。
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="news_page_events",
        verbose_name="ユーザー",
    )

    path = models.CharField(
        "閲覧ページ",
        max_length=500,
        blank=True,
    )

    accessed_at = models.DateTimeField(
        "アクセス日時",
        auto_now_add=True,
        db_index=True,
    )

    is_visit_start = models.BooleanField(
        "新しい訪問",
        default=False,
    )

    class Meta:

        verbose_name = "ログインユーザー News利用履歴"
        verbose_name_plural = "ログインユーザー News利用履歴"

        ordering = [
            "-accessed_at",
        ]

        indexes = [

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
            f"{self.path} | "
            f"{self.accessed_at}"
        )


# =========================================================
# Authenticated News Article Click Analytics
# =========================================================

class UserNewsArticleClick(models.Model):
    """
    ログインユーザーがSwiss Newsから
    元記事をクリックした履歴。
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="news_article_clicks",
        verbose_name="ユーザー",
    )

    article_id = models.PositiveBigIntegerField(
        "記事ID",
        db_index=True,
    )

    article_title = models.CharField(
        "記事タイトル",
        max_length=500,
    )

    source_name = models.CharField(
        "ニュースソース",
        max_length=200,
        blank=True,
    )

    destination_url = models.URLField(
        "リンク先",
        max_length=2000,
    )

    clicked_at = models.DateTimeField(
        "クリック日時",
        auto_now_add=True,
        db_index=True,
    )

    class Meta:

        verbose_name = "ログインユーザー News記事クリック"
        verbose_name_plural = "ログインユーザー News記事クリック"

        ordering = [
            "-clicked_at",
        ]

        indexes = [

            models.Index(
                fields=[
                    "user",
                    "clicked_at",
                ],
            ),

            models.Index(
                fields=[
                    "article_id",
                    "clicked_at",
                ],
            ),

        ]

    def __str__(self):

        return (
            f"{self.user.username} | "
            f"{self.article_title} | "
            f"{self.clicked_at}"
        )