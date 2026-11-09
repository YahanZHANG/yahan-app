from django.conf import settings
from django.db import models

from .seasons import THEMES


class PortalAppPreference(models.Model):
    """
    Portalに表示するアプリと、
    ユーザーごとの表示順を保存する。
    """

    class AppKey(models.TextChoices):

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

        EVENTS = (
            "events",
            "イベント・日程調整",
        )

        CHAT = (
            "chat",
            "チャット",
        )

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


class AppAccessRequest(models.Model):

    class AppKey(models.TextChoices):

        FEEDING = (
            "feeding",
            "離乳食記録",
        )

        VACCINATION = (
            "vaccination",
            "ワクチン記録",
        )

        GAMES = (
            "games",
            "ミニゲーム",
        )

        CHAT = (
            "chat",
            "チャット",
        )

        BOARD = (
            "board",
            "掲示板",
        )


    class Status(models.TextChoices):

        PENDING = (
            "pending",
            "確認待ち",
        )

        APPROVED = (
            "approved",
            "承認",
        )

        DECLINED = (
            "declined",
            "見送り",
        )


    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="app_access_requests",
    )

    app_key = models.CharField(
        "利用希望アプリ",
        max_length=30,
        choices=AppKey.choices,
    )

    status = models.CharField(
        "ステータス",
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    requested_path = models.CharField(
        "申請元URL",
        max_length=500,
        blank=True,
    )

    created_at = models.DateTimeField(
        "申請日時",
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        "更新日時",
        auto_now=True,
    )


    class Meta:

        ordering = [
            "-created_at",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "user",
                    "app_key",
                ],
                name="unique_app_access_request_per_user",
            ),
        ]


    def __str__(self):

        return (
            f"{self.user.username} - "
            f"{self.get_app_key_display()}"
        )

class PortalAnnouncement(models.Model):
    """
    Yappトップ (/) の一番上に出すお知らせ。管理画面から追加する。
    新しい3件まで、追加から14日間表示し、×で閉じたものはその端末では出なくなる。
    """

    SHOW_DAYS = 14
    MAX_SHOWN = 3

    message = models.CharField(
        "お知らせ",
        max_length=200,
    )

    link = models.CharField(
        "リンク先（なくてもOK）",
        max_length=300,
        blank=True,
        help_text="例: /help/ （困ったときは）",
    )

    is_active = models.BooleanField(
        "表示する",
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "Yappトップのお知らせ"
        verbose_name_plural = "Yappトップのお知らせ"
        ordering = ["-created_at"]

    def __str__(self):
        return self.message

    @classmethod
    def current(cls):
        """Yappトップに出すお知らせ (新しい順、最大 MAX_SHOWN 件)"""

        from datetime import timedelta

        from django.utils import timezone

        since = timezone.now() - timedelta(days=cls.SHOW_DAYS)

        return cls.objects.filter(is_active=True, created_at__gte=since)[:cls.MAX_SHOWN]


class AppIdea(models.Model):
    """Yappトップの「アプリのアイデア募集」から届いたアイデア。"""

    idea = models.TextField(
        "アイデア",
        max_length=1000,
    )

    contact = models.CharField(
        "お名前・連絡先（任意）",
        max_length=200,
        blank=True,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="送信したアカウント",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    handled = models.BooleanField(
        "確認済み",
        default=False,
    )

    created_at = models.DateTimeField(
        "送信日時",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "アプリのアイデア"
        verbose_name_plural = "アプリのアイデア"
        ordering = ["-created_at"]

    def __str__(self):
        return self.idea[:40]


class PortalSettings(models.Model):
    """Yappトップの表示設定。1件だけ。"""

    SEASON_CHOICES = [("auto", "自動 (日付に合わせる)")] + [
        (key, theme["name"]) for key, theme in THEMES.items()
    ]

    season = models.CharField(
        "季節のデザイン",
        max_length=20,
        choices=SEASON_CHOICES,
        default="auto",
        help_text="試しに見たいときや、時期をずらしたいときに固定できます。ふだんは「自動」のままで大丈夫です。",
    )

    class Meta:
        verbose_name = "Yappトップの表示設定"
        verbose_name_plural = "Yappトップの表示設定"

    def __str__(self):
        return "Yappトップの表示設定"

    @classmethod
    def load(cls):
        settings_row, _ = cls.objects.get_or_create(pk=1)
        return settings_row


class PortalThemeText(models.Model):
    """Yappトップの大きなキャッチ。季節・イベントごとに管理画面から変えられる。"""

    theme = models.CharField(
        "季節・イベント",
        max_length=30,
        unique=True,
        choices=[(key, theme["name"]) for key, theme in THEMES.items()],
    )

    title = models.CharField(
        "1行目",
        max_length=40,
        blank=True,
        help_text="空にすると、元の文言に戻ります",
    )

    headline = models.CharField(
        "2行目（大きい文字）",
        max_length=40,
        blank=True,
        help_text="空にすると、元の文言に戻ります",
    )

    class Meta:
        verbose_name = "Yappトップのキャッチ"
        verbose_name_plural = "Yappトップのキャッチ"

    def __str__(self):
        return self.get_theme_display()

    @classmethod
    def ensure_all(cls):
        """まだ行がない季節・イベントの行を、元の文言で作る。"""

        existing = set(cls.objects.values_list("theme", flat=True))
        cls.objects.bulk_create([
            cls(theme=key, title=theme["title"], headline=theme["headline"])
            for key, theme in THEMES.items()
            if key not in existing
        ])


class AppPopup(models.Model):
    """
    各アプリを開いたときに出すポップアップ。管理画面で中身・出すかどうか・頻度を決める。
    templates/includes/app_popup.html (portal/templatetags/app_popup.py) が表示する。
    同じアプリで出すものが複数あるときは、並び順の小さいものから1回に1つだけ。
    内容を保存し直すと「1回だけ」のものも、もう一度出る。
    """

    APP_CHOICES = [
        ("news", "スイスニュース"),
        ("washoku", "スイスで和食"),
        ("swiss-board", "スイス知恵袋（掲示板）"),
        ("outings", "おでかけ"),
        ("top", "Yappトップ"),
    ]

    FREQUENCY_ONCE = "once"
    FREQUENCY_DAILY = "daily"
    FREQUENCY_EVERY = "every"

    FREQUENCY_CHOICES = [
        (FREQUENCY_ONCE, "1回だけ（内容を更新したら、また出る）"),
        (FREQUENCY_DAILY, "1日1回"),
        (FREQUENCY_EVERY, "開くたび"),
    ]

    AUDIENCE_CHOICES = [
        ("all", "全員"),
        ("guests", "ログインしていない人だけ"),
        ("members", "会員だけ"),
    ]

    app = models.CharField("アプリ", max_length=20, choices=APP_CHOICES)

    is_active = models.BooleanField("ポップアップとして出す", default=False)

    emoji = models.CharField("絵文字（なくてもOK）", max_length=8, blank=True, help_text="例: 🎄")

    title = models.CharField("タイトル", max_length=80)

    body = models.TextField("本文", max_length=1000, blank=True, help_text="改行はそのまま表示されます。")

    image_url = models.URLField("画像のURL（なくてもOK）", max_length=500, blank=True)

    button_label = models.CharField(
        "ボタンの文字（なくてもOK）", max_length=30, blank=True, help_text="例: 詳しく見る",
    )

    link = models.CharField(
        "ボタンのリンク先（なくてもOK）", max_length=300, blank=True,
        help_text="例: /washoku/polls/ 。ボタンの文字とリンク先の両方を入れると、ボタンが出ます。",
    )

    open_in_browser = models.BooleanField(
        "ボタンをブラウザで開く", default=True,
        help_text="オン: ホーム画面のアプリで見ていても、Safari や Chrome などのブラウザで開きます。オフ: 今の画面のまま開きます。",
    )

    frequency = models.CharField("出す頻度", max_length=10, choices=FREQUENCY_CHOICES, default=FREQUENCY_ONCE)

    audience = models.CharField("出す相手", max_length=10, choices=AUDIENCE_CHOICES, default="all")

    home_only = models.BooleanField("HOMEを開いたときだけ出す", default=True, help_text="オフにすると、アプリのどのページでも出ます。")

    starts_at = models.DateTimeField("表示開始（なくてもOK）", null=True, blank=True)

    ends_at = models.DateTimeField("表示終了（なくてもOK）", null=True, blank=True)

    order = models.PositiveIntegerField("並び順", default=0, help_text="小さいものから先に出ます。")

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField("更新", auto_now=True)

    class Meta:
        verbose_name = "ポップアップ"
        verbose_name_plural = "ポップアップ（各アプリ）"
        ordering = ["app", "order", "-updated_at"]

    def __str__(self):
        return self.title

    @property
    def version(self):
        """閉じたことを覚えておく鍵。内容を保存し直すと変わる。"""

        return f"{self.pk}-{int(self.updated_at.timestamp())}"

    @property
    def has_button(self):
        return bool(self.button_label and self.link)

    @classmethod
    def for_request(cls, request):
        """このページで出す候補 (並び順)。どれを出すかは、端末に残した記録を見てブラウザが決める。"""

        from django.db.models import Q
        from django.utils import timezone

        first = request.path.lstrip("/").split("/", 1)[0]
        app = first or "top"
        if app not in dict(cls.APP_CHOICES):
            return []
        home = request.path == ("/" if app == "top" else f"/{app}/")

        now = timezone.now()
        popups = cls.objects.filter(app=app, is_active=True).filter(
            Q(starts_at__isnull=True) | Q(starts_at__lte=now),
            Q(ends_at__isnull=True) | Q(ends_at__gt=now),
        )
        if not home:
            popups = popups.filter(home_only=False)
        if request.user.is_authenticated:
            popups = popups.exclude(audience="guests")
        else:
            popups = popups.exclude(audience="members")
        return list(popups[:5])
