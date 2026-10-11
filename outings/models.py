
from django.conf import settings
from django.db import models
from django.db.models import Q


class EventCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class EventTag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class EventSource(models.Model):
    name = models.CharField(max_length=150, unique=True)
    website_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name


class EventLocation(models.Model):
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=300, blank=True)
    city = models.CharField(max_length=120)
    canton = models.CharField(max_length=10)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.name} ({self.city})"


class Event(models.Model):

    class EventType(models.TextChoices):
        ONE_TIME = "one_time", "単発"
        RECURRING = "recurring", "定期開催"
        LONG_RUNNING = "long_running", "長期開催"

    class Status(models.TextChoices):
        DRAFT = "draft", "下書き"
        PENDING = "pending", "承認待ち"
        PUBLISHED = "published", "公開中"
        REJECTED = "rejected", "却下"
        CANCELLED = "cancelled", "中止"

    class LanguageBarrier(models.TextChoices):
        NONE = "none", "言語ほぼ不要"
        ENGLISH = "english", "英語"
        JAPANESE = "japanese", "日本語"

        GERMAN_SOME = "german_some", "ドイツ語（A2以下）"
        GERMAN_REQUIRED = "german_required", "ドイツ語（B1以上）"

        FRENCH_SOME = "french_some", "フランス語（A2以下）"
        FRENCH_REQUIRED = "french_required", "フランス語（B1以上）"

        ITALIAN_SOME = "italian_some", "イタリア語（A2以下）"
        ITALIAN_REQUIRED = "italian_required", "イタリア語（B1以上）"

        UNKNOWN = "unknown", "不明"

    title = models.CharField(max_length=250)
    title_original = models.CharField(max_length=250, blank=True)

    summary_ja = models.TextField(blank=True)
    description_original = models.TextField(blank=True)

    event_type = models.CharField(
        max_length=20,
        choices=EventType.choices,
        default=EventType.ONE_TIME,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    category = models.ForeignKey(
        EventCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )

    tags = models.ManyToManyField(
        EventTag,
        blank=True,
        related_name="events",
    )

    location = models.ForeignKey(
        EventLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )

    language_barrier = models.CharField(
        max_length=20,
        choices=LanguageBarrier.choices,
        default=LanguageBarrier.UNKNOWN,
    )

    is_free = models.BooleanField(default=False)
    price_text = models.CharField(max_length=150, blank=True)

    is_indoor = models.BooleanField(default=False)
    is_outdoor = models.BooleanField(default=False)

    original_url = models.URLField(max_length=1000, blank=True)
    image_url = models.URLField(max_length=1000, blank=True)

    source = models.ForeignKey(
        EventSource,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )

    external_id = models.CharField(
        max_length=200,
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="outings_events",
    )

    ai_processed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "external_id"],
                condition=(
                    Q(source__isnull=False)
                    & ~Q(external_id="")
                ),
                name="unique_outings_source_external_id",
            ),
        ]

    def __str__(self):
        return self.title


class EventOccurrence(models.Model):

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="occurrences",
    )

    comment = models.ForeignKey(
        "OutingsComment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )

    start_at = models.DateTimeField()
    end_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    is_cancelled = models.BooleanField(default=False)

    class Meta:
        ordering = ["start_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "start_at"],
                name="unique_outings_event_start",
            ),
        ]

    def __str__(self):
        return f"{self.event.title} - {self.start_at}"


import uuid


class EventHeart(models.Model):
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="hearts",
    )
    visitor_id = models.UUIDField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["event", "visitor_id"],
                name="unique_outings_event_heart",
            )
        ]

    def __str__(self):
        return f"Heart: {self.event_id}"


class OutingsPreference(models.Model):
    visitor_id = models.UUIDField(
        unique=True,
        default=uuid.uuid4,
        editable=False,
    )
    favorite_regions = models.JSONField(default=list)
    personalization_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.visitor_id)


# =========================================================
# Outings Notification
# =========================================================

class OutingsNotification(models.Model):

    class Kind(models.TextChoices):
        COMMENT = "comment", "コメント"
        REPLY = "reply", "返信"
        APPROVED = "approved", "イベント掲載承認"
        REJECTED = "rejected", "イベント掲載却下"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="outings_notifications",
    )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="outings_sent_notifications",
    )

    event = models.ForeignKey(
        Event,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )

    kind = models.CharField(
        max_length=20,
        choices=Kind.choices,
    )

    message = models.CharField(
        max_length=250,
        blank=True,
    )

    is_read = models.BooleanField(
        default=False,
        db_index=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(
                fields=["recipient", "is_read"],
                name="outings_notice_unread_idx",
            ),
        ]

    def __str__(self):
        return f"Outings Notification {self.pk}"



# =========================================================
# Outings Comment
# =========================================================

class OutingsComment(models.Model):

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="comments",
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="outings_comments",
    )

    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replies",
    )

    body = models.TextField(
        max_length=500,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    # Soft delete
    is_deleted = models.BooleanField(
        default=False,
        db_index=True,
    )

    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="outings_deleted_comments",
    )

    deleted_reason = models.CharField(
        max_length=200,
        blank=True,
    )

    class Meta:
        ordering = ["created_at", "pk"]
        indexes = [
            models.Index(
                fields=["event", "created_at"],
                name="outings_comment_event_idx",
            ),
        ]

    def __str__(self):
        return f"Comment {self.pk} on event {self.event_id}"
