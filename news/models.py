from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Topic(models.Model):
    name = models.CharField(
        max_length=100,
        unique=True,
    )

    slug = models.SlugField(
        max_length=100,
        unique=True,
    )

    icon = models.CharField(
        max_length=20,
        blank=True,
    )

    display_order = models.PositiveIntegerField(
        default=0,
    )

    is_active = models.BooleanField(
        default=True,
    )

    class Meta:
        ordering = [
            "display_order",
            "name",
        ]

    def __str__(self):
        return self.name


class NewsSource(models.Model):
    LANGUAGE_CHOICES = [
        ("ja", "日本語"),
        ("de", "Deutsch"),
        ("fr", "Français"),
        ("it", "Italiano"),
        ("en", "English"),
        ("multi", "Multilingual"),
    ]

    name = models.CharField(
        max_length=100,
        unique=True,
    )

    website_url = models.URLField()

    feed_url = models.URLField(
        blank=True,
    )

    language = models.CharField(
        max_length=10,
        choices=LANGUAGE_CHOICES,
        default="de",
    )

    is_active = models.BooleanField(
        default=True,
    )

    display_order = models.PositiveIntegerField(
        default=0,
    )

    def __str__(self):
        return self.name

class Region(models.Model):

    name = models.CharField(
        max_length=100,
        unique=True,
    )

    slug = models.SlugField(
        max_length=100,
        unique=True,
    )

    icon = models.CharField(
        max_length=20,
        blank=True,
    )

    display_order = models.PositiveIntegerField(
        default=0,
    )

    is_active = models.BooleanField(
        default=True,
    )

    class Meta:
        ordering = [
            "display_order",
            "name",
        ]

    def __str__(self):
        return self.name


class Article(models.Model):
    LANGUAGE_CHOICES = [    
        ("ja", "日本語"),
        ("de", "Deutsch"),
        ("fr", "Français"),
        ("it", "Italiano"),
        ("en", "English"),
        ("other", "Other"),
    ]

    source = models.ForeignKey(
        NewsSource,
        on_delete=models.CASCADE,
        related_name="articles",
    )

    source_url = models.URLField(
        unique=True,
    )

    original_language = models.CharField(
        max_length=10,
        choices=LANGUAGE_CHOICES,
    )

    title_original = models.TextField()

    title_ja = models.TextField(
        blank=True,
    )

    summary_original = models.TextField(
        blank=True,
    )

    summary_ja = models.TextField(
        blank=True,
    )

    topics = models.ManyToManyField(
        Topic,
        related_name="articles",
        blank=True,
    )

    regions = models.ManyToManyField(
        Region,
        related_name="articles",
        blank=True,
    )

    published_at = models.DateTimeField()

    fetched_at = models.DateTimeField(
        auto_now_add=True,
    )

    is_featured = models.BooleanField(
        default=False,
    )

    ai_processed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    ai_model = models.CharField(
        max_length=100,
        blank=True,
    )

    ai_error = models.TextField(
        blank=True,
    )

    ai_attempts = models.PositiveSmallIntegerField(
        default=0,
    )

    # 重複チェックをした日時（まだなら空）
    dedupe_checked_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # 暮らしのお知らせ（スト・運休・締め切り・営業時間など）。
    # AI が翻訳のときに判定する。
    life_alert = models.BooleanField(
        "暮らしのお知らせ",
        default=False,
        db_index=True,
    )

    # 同じ出来事を扱う代表記事。
    # 設定されている記事は一覧に表示せず、
    # 代表記事の出典として表示する。
    duplicate_of = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="duplicates",
    )

    class Meta:
        ordering = [
            "-published_at",
            "-id",
        ]

    def __str__(self):
        return self.title_ja or self.title_original

    @property
    def source_articles(self):
        """
        この記事と重複記事を、ソースごとに1件ずつ返す。
        一覧では duplicates__source を prefetch して使う。
        """

        result = []
        seen_source_ids = set()

        for article in [self, *self.duplicates.all()]:

            if article.source_id in seen_source_ids:
                continue

            seen_source_ids.add(
                article.source_id
            )

            result.append(
                article
            )

        return result


class Favorite(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="news_favorites",
    )

    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name="favorites",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = [
            "-created_at",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "user",
                    "article",
                ],
                name="unique_news_favorite",
            )
        ]

    def clean(self):
        if self.pk:
            return

        count = Favorite.objects.filter(
            user=self.user,
        ).count()

        if count >= 10:
            raise ValidationError(
                "お気に入りは10件まで登録できます。"
            )

    def __str__(self):
        return f"{self.user} - {self.article}"


class NewsPreference(models.Model):
    DISPLAY_LANGUAGE_CHOICES = [
        ("ja", "日本語"),
        ("original", "元の言語"),
    ]

    FONT_SIZE_CHOICES = [
        ("small", "小"),
        ("medium", "標準"),
        ("large", "大"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="news_preference",
    )

    display_language = models.CharField(
        max_length=20,
        choices=DISPLAY_LANGUAGE_CHOICES,
        default="ja",
    )

    font_size = models.CharField(
        max_length=20,
        choices=FONT_SIZE_CHOICES,
        default="medium",
    )

    dark_mode = models.BooleanField(
        default=False,
        verbose_name="ダークモード",
    )

    show_life_on_home = models.BooleanField(
        default=True,
        verbose_name="HOMEに暮らしのニュースを表示",
    )

    hidden_topics = models.ManyToManyField(
        Topic,
        blank=True,
        related_name="hidden_by_users",
    )

    hidden_regions = models.ManyToManyField(
        Region,
        blank=True,
        related_name="hidden_by_users",
    )

    hidden_sources = models.ManyToManyField(
        NewsSource,
        blank=True,
        related_name="hidden_by_users",
    )

    def __str__(self):
        return f"{self.user} news settings"

class NewsDigest(models.Model):

    PERIOD_CHOICES = [
        ("morning", "朝のまとめ"),
        ("late_morning", "午前のまとめ"),
        ("afternoon", "午後のまとめ"),
        ("evening", "夜のまとめ"),
    ]

    digest_date = models.DateField()

    period = models.CharField(
        max_length=20,
        choices=PERIOD_CHOICES,
    )

    summary_ja = models.TextField()

    highlights = models.JSONField(
        default=list,
        blank=True,
    )

    article_count = models.PositiveIntegerField(
        default=0,
    )

    source_from = models.DateTimeField()

    source_to = models.DateTimeField()

    generated_at = models.DateTimeField(
        auto_now=True,
    )

    ai_model = models.CharField(
        max_length=100,
        blank=True,
    )

    input_tokens = models.PositiveIntegerField(
        default=0,
    )

    output_tokens = models.PositiveIntegerField(
        default=0,
    )

    class Meta:
        ordering = [
            "-generated_at",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "digest_date",
                    "period",
                ],
                name="unique_news_digest_period",
            )
        ]

    def __str__(self):
        return (
            f"{self.digest_date} "
            f"{self.get_period_display()}"
        )

# =========================================================
# Swiss News Push Subscription
# =========================================================

from django.conf import settings as django_settings
from django.db import models as django_models


class NewsPushSubscription(django_models.Model):

    FREQUENCY_CHOICES = [
        ("every", "更新のたび（1日4回）"),
        ("daily", "1日1回（朝）"),
    ]

    # 未ログインの端末も登録できるよう null を許可
    user = django_models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=django_models.CASCADE,
        related_name="news_push_subscriptions",
        null=True,
        blank=True,
    )

    endpoint = django_models.TextField(
        unique=True,
    )

    p256dh = django_models.TextField()

    auth = django_models.TextField()

    frequency = django_models.CharField(
        "通知の頻度",
        max_length=10,
        choices=FREQUENCY_CHOICES,
        default="every",
    )

    # 暮らしのお知らせを受け取る地域（なし = 受け取らない）。
    # 住んでいる所と通勤先など、いくつでも選べる。
    alert_regions = django_models.ManyToManyField(
        Region,
        blank=True,
        related_name="push_subscriptions",
        verbose_name="暮らしのお知らせの地域",
    )

    created_at = django_models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = django_models.DateTimeField(
        auto_now=True,
    )

    class Meta:

        verbose_name = "ニュースPush登録"

        verbose_name_plural = "ニュースPush登録"

    def __str__(self):

        owner = (
            self.user.username
            if self.user
            else "anonymous"
        )

        return (
            f"{owner} - "
            f"Push subscription {self.pk}"
        )

# =========================================================
# News Push Batch
# =========================================================

class NewsPushBatch(django_models.Model):

    batch_key = django_models.CharField(
        max_length=150,
        unique=True,
    )

    started_at = django_models.DateTimeField(
        auto_now_add=True,
    )

    completed_at = django_models.DateTimeField(
        null=True,
        blank=True,
    )

    sent_count = django_models.PositiveIntegerField(
        default=0,
    )

    failed_count = django_models.PositiveIntegerField(
        default=0,
    )

    class Meta:

        verbose_name = "ニュースPush送信履歴"

        verbose_name_plural = "ニュースPush送信履歴"

    def __str__(self):

        return self.batch_key


class NewsFeedback(models.Model):

    message = models.TextField(
        "コメント",
        max_length=1000,
    )

    created_at = models.DateTimeField(
        "送信日時",
        auto_now_add=True,
    )

    is_read = models.BooleanField(
        "確認済み",
        default=False,
    )

    class Meta:
        verbose_name = "Swiss News コメント"
        verbose_name_plural = "Swiss News コメント"
        ordering = [
            "-created_at",
        ]

    def __str__(self):
        return self.message[:50]


# =========================================================
# Swiss News support requests
# =========================================================

class SupportRequest(models.Model):

    class Method(models.TextChoices):
        BANK = (
            "bank",
            "銀行口座で応援",
        )
        OTHER = (
            "other",
            "その他の方法で応援",
        )

    class BankCountry(models.TextChoices):
        CH = (
            "ch",
            "スイスの銀行口座",
        )
        JP = (
            "jp",
            "日本の銀行口座",
        )

    method = models.CharField(
        max_length=20,
        choices=Method.choices,
    )

    bank_country = models.CharField(
        max_length=10,
        choices=BankCountry.choices,
        blank=True,
    )

    name = models.CharField(
        max_length=100,
        blank=True,
    )

    email = models.EmailField()

    message = models.TextField(
        blank=True,
    )

    is_read = models.BooleanField(
        default=False,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = [
            "-created_at",
        ]

        verbose_name = (
            "Swiss News 応援問い合わせ"
        )

        verbose_name_plural = (
            "Swiss News 応援問い合わせ"
        )

    def __str__(self):

        return (
            f"{self.get_method_display()} "
            f"- {self.email}"
        )

class NewsAnnouncement(models.Model):
    """
    ヘッダーと記事の間に控えめに出す「更新のお知らせ」。
    管理画面から追加する。表示されるのは最新の1件だけ。
    """

    SHOW_DAYS = 14

    message = models.CharField(
        "お知らせ",
        max_length=200,
    )

    link = models.CharField(
        "リンク先（なくてもOK）",
        max_length=300,
        blank=True,
        help_text=(
            "例: /news/life/ （暮らしのお知らせ）、/news/settings/ （設定）、"
            "https://… （ほかのサイト）"
        ),
    )

    is_active = models.BooleanField(
        "表示する",
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = [
            "-created_at",
        ]

        verbose_name = (
            "Swiss News 更新のお知らせ"
        )

        verbose_name_plural = (
            "Swiss News 更新のお知らせ"
        )

    def __str__(self):

        return self.message
