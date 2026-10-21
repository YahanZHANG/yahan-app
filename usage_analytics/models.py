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
    ログインしていない公開Swiss News閲覧者の
    匿名アクセス履歴。

    visitor_id:
        ブラウザ単位の長期匿名ID

    visit_id:
        30分無操作で区切る1回の訪問ID
    """

    class DeviceType(models.TextChoices):

        DESKTOP = (
            "desktop",
            "Desktop",
        )

        MOBILE = (
            "mobile",
            "Mobile",
        )

        TABLET = (
            "tablet",
            "Tablet",
        )

        OTHER = (
            "other",
            "Other",
        )


    visitor_id = models.UUIDField(
        "匿名訪問者ID",
        db_index=True,
    )


    visit_id = models.UUIDField(
        "訪問ID",
        null=True,
        blank=True,
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


    is_new_visitor = models.BooleanField(
        "初回訪問者",
        default=False,
        db_index=True,
    )


    referrer_host = models.CharField(
        "流入元ホスト",
        max_length=255,
        blank=True,
        default="",
    )


    utm_source = models.CharField(
        "UTM source",
        max_length=100,
        blank=True,
        default="",
    )


    utm_medium = models.CharField(
        "UTM medium",
        max_length=100,
        blank=True,
        default="",
    )


    utm_campaign = models.CharField(
        "UTM campaign",
        max_length=150,
        blank=True,
        default="",
    )


    device_type = models.CharField(
        "デバイス",
        max_length=20,
        choices=DeviceType.choices,
        default=DeviceType.OTHER,
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

            models.Index(
                fields=[
                    "visit_id",
                    "accessed_at",
                ],
            ),

            models.Index(
                fields=[
                    "accessed_at",
                    "is_new_visitor",
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
    公開Swiss Newsから元記事へのクリック。
    """

    visitor_id = models.UUIDField(
        "匿名訪問者ID",
        db_index=True,
    )


    visit_id = models.UUIDField(
        "訪問ID",
        null=True,
        blank=True,
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


    origin_path = models.CharField(
        "クリック元ページ",
        max_length=500,
        blank=True,
        default="",
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
                    "visit_id",
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

# =========================================================
# Page views (all apps)
# =========================================================

class PageView(models.Model):
    """
    全アプリ共通のページ閲覧記録。

    visitor_id:
        ブラウザ単位の長期匿名ID (cookie)。ログインしていても付く。

    visit_id:
        30分操作がなければ区切る1回の訪問。

    流入元 (source_*, referrer_host, utm_*) は
    訪問の最初のページ (is_visit_start=True) にだけ入る。
    """

    visitor_id = models.UUIDField("訪問者ID")

    visit_id = models.UUIDField("訪問ID")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="page_views",
        verbose_name="ユーザー",
    )

    app_key = models.CharField("アプリ", max_length=40)

    path = models.CharField("ページ", max_length=300, blank=True)

    # bulk_create (過去データの引き継ぎ) で日時を指定できるよう auto_now_add は使わない
    accessed_at = models.DateTimeField("日時", default=timezone.now)

    is_visit_start = models.BooleanField("訪問の最初", default=False)

    is_new_visitor = models.BooleanField("初めての訪問者", default=False)

    source_type = models.CharField("流入元の種類", max_length=20, blank=True, default="")

    source_label = models.CharField("流入元", max_length=120, blank=True, default="")

    referrer_host = models.CharField("リファラー", max_length=255, blank=True, default="")

    utm_source = models.CharField(max_length=100, blank=True, default="")

    utm_medium = models.CharField(max_length=100, blank=True, default="")

    utm_campaign = models.CharField(max_length=150, blank=True, default="")

    device_type = models.CharField("デバイス", max_length=20, default="other")

    class Meta:

        verbose_name = "ページ閲覧"
        verbose_name_plural = "ページ閲覧"

        # 既定の並び順は付けない (付けると DISTINCT や集計に並び順の列が混ざる)

        indexes = [
            models.Index(fields=["accessed_at"]),
            models.Index(fields=["app_key", "accessed_at"]),
            models.Index(fields=["visitor_id", "accessed_at"]),
            models.Index(fields=["visit_id"]),
            models.Index(fields=["user", "accessed_at"]),
        ]

    def __str__(self):

        return f"{self.visitor_id} | {self.path} | {self.accessed_at}"


class AnalyticsExclusion(models.Model):
    """
    集計から外すアカウント (自分や家族の確認用アカウントなど)。
    そのアカウントでログインしたことがあるブラウザの閲覧もまとめて外す。
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="analytics_exclusion",
        verbose_name="ユーザー",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:

        verbose_name = "集計から外すアカウント"
        verbose_name_plural = "集計から外すアカウント"

    def __str__(self):

        return self.user.username
