from django.conf import settings
from django.db import models
from django.urls import reverse


# =========================================================
# Swiss Board Post
# =========================================================

class SwissBoardPost(models.Model):

    # -----------------------------------------------------
    # Categories
    # -----------------------------------------------------

    class Category(models.TextChoices):

        MARKETPLACE = (
            "marketplace",
            "売買・譲渡・レンタル",
        )

        HOUSING = (
            "housing",
            "不動産・住まい",
        )

        JOBS = (
            "jobs",
            "求人・仕事探し",
        )

        FRIENDS = (
            "friends",
            "仲間募集",
        )

        EVENTS = (
            "events",
            "イベント",
        )

        LESSONS = (
            "lessons",
            "レッスン・習い事",
        )

        PARENTING = (
            "parenting",
            "育児・教育",
        )

        SERVICES = (
            "services",
            "サービス・ビジネス",
        )

        RECOMMENDATIONS = (
            "recommendations",
            "みんなのおすすめ",
        )

        QUESTIONS = (
            "questions",
            "質問・雑談",
        )

    # -----------------------------------------------------
    # Status
    # -----------------------------------------------------

    class Status(models.TextChoices):

        DRAFT = (
            "draft",
            "下書き",
        )

        PUBLISHED = (
            "published",
            "公開",
        )

        HIDDEN = (
            "hidden",
            "非公開",
        )

    # -----------------------------------------------------
    # Author
    # -----------------------------------------------------

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="swiss_board_posts",
        verbose_name="投稿者",
    )

    # -----------------------------------------------------
    # Content
    # -----------------------------------------------------

    title = models.CharField(
        "タイトル",
        max_length=30,
    )

    body = models.TextField(
        "本文",
        max_length=500,
    )

    category = models.CharField(
        "カテゴリー",
        max_length=30,
        choices=Category.choices,
        db_index=True,
    )

    subcategory = models.CharField(
        "サブカテゴリー",
        max_length=100,
        blank=True,
    )

    region = models.CharField(
        "地域",
        max_length=100,
        blank=True,
        db_index=True,
    )

    # -----------------------------------------------------
    # Publication
    # -----------------------------------------------------

    status = models.CharField(
        "公開状態",
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    # -----------------------------------------------------
    # Timestamps
    # -----------------------------------------------------

    created_at = models.DateTimeField(
        "作成日時",
        auto_now_add=True,
        db_index=True,
    )

    updated_at = models.DateTimeField(
        "更新日時",
        auto_now=True,
    )

    # -----------------------------------------------------
    # Meta
    # -----------------------------------------------------

    class Meta:

        verbose_name = "スイス掲示板の投稿"
        verbose_name_plural = "スイス掲示板の投稿"

        ordering = [
            "-created_at",
            "-id",
        ]

        indexes = [
            models.Index(
                fields=[
                    "status",
                    "-created_at",
                ],
            ),
        ]

    # -----------------------------------------------------
    # Methods
    # -----------------------------------------------------

    def __str__(self):
        return self.title

    @classmethod
    def public_posts(cls):
        """
        公開中の投稿のみを取得する。
        """
        return cls.objects.filter(
            status=cls.Status.PUBLISHED,
        )

# =========================================================
# Swiss Board Profile
# =========================================================

class SwissBoardProfile(models.Model):

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="swiss_board_profile",
        verbose_name="ユーザー",
    )

    display_name = models.CharField(
        "掲示板の表示名",
        max_length=30,
        blank=True,
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
        verbose_name = "掲示板プロフィール"
        verbose_name_plural = "掲示板プロフィール"

    def __str__(self):
        return self.display_name or "掲示板ユーザー"

# =========================================================
# Swiss Board Comment
# =========================================================

class SwissBoardComment(models.Model):

    post = models.ForeignKey(
        SwissBoardPost,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="投稿",
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="swiss_board_comments",
        verbose_name="投稿者",
    )

    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replies",
        verbose_name="返信先コメント",
    )

    body = models.TextField(
        "コメント本文",
        max_length=500,
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
        verbose_name = "掲示板コメント"
        verbose_name_plural = "掲示板コメント"
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"Comment {self.pk} on post {self.post_id}"


# =========================================================
# Swiss Board Notification
# =========================================================

class SwissBoardNotification(models.Model):

    class Kind(models.TextChoices):
        COMMENT = "comment", "コメント"
        REPLY = "reply", "返信"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="swiss_board_notifications",
        verbose_name="通知先",
    )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="swiss_board_sent_notifications",
        verbose_name="通知のきっかけとなった人",
    )

    comment = models.ForeignKey(
        SwissBoardComment,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="対象コメント",
    )

    kind = models.CharField(
        "通知種類",
        max_length=20,
        choices=Kind.choices,
    )

    is_read = models.BooleanField(
        "既読",
        default=False,
    )

    created_at = models.DateTimeField(
        "通知日時",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "掲示板通知"
        verbose_name_plural = "掲示板通知"
        ordering = ["-created_at", "-pk"]

        constraints = [
            models.UniqueConstraint(
                fields=["recipient", "comment"],
                name="sb_unique_recipient_comment_notice",
            ),
        ]

    def __str__(self):
        return (
            f"Notification {self.pk}: "
            f"{self.recipient_id}"
        )