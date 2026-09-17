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

    class Meta:
        ordering = [
            "-published_at",
            "-id",
        ]

    def __str__(self):
        return self.title_ja or self.title_original


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

    hidden_topics = models.ManyToManyField(
        Topic,
        blank=True,
        related_name="hidden_by_users",
    )

    def __str__(self):
        return f"{self.user} news settings"

class NewsDigest(models.Model):

    PERIOD_CHOICES = [
        ("morning", "朝"),
        ("afternoon", "午後"),
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