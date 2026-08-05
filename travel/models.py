from django.conf import settings
from django.db import models
from decimal import Decimal
from django.utils import timezone
from django.core.validators import MinValueValidator


class Schedule(models.Model):
    """旅行や家族の予定を保存するモデル。"""

    title = models.CharField(
        "予定名",
        max_length=200,
    )

    start_at = models.DateTimeField(
        "開始日時",
    )

    end_at = models.DateTimeField(
        "終了日時",
        blank=True,
        null=True,
    )

    location = models.CharField(
        "場所",
        max_length=200,
        blank=True,
    )

    class Person(models.TextChoices):
        BABY = "baby", "赤ちゃん"
        MAMA = "mama", "ママ"
        PAPA = "papa", "パパ"
        FAMILY = "family", "家族全員"
        OTHER = "other", "その他"

    note = models.TextField(
        "補足",
        blank=True,
    )

    is_important = models.BooleanField(
        "重要な予定",
        default=False,
    )

    person = models.CharField(
        "誰の予定",
        max_length=20,
        choices=Person.choices,
        default=Person.FAMILY,
    )

    created_by = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    verbose_name="作成者",
    on_delete=models.SET_NULL,
    blank=True,
    null=True,
    related_name="created_schedules",
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
        verbose_name = "予定"
        verbose_name_plural = "予定"
        ordering = ["start_at"]

    def __str__(self):
        return self.title


class Task(models.Model):
    """家族へのお願いやToDoを保存するモデル。"""

    class Priority(models.TextChoices):
        LOW = "low", "低"
        NORMAL = "normal", "通常"
        HIGH = "high", "高"

    title = models.CharField(
        "やること",
        max_length=200,
    )

    assigned_to = models.CharField(
        "担当者",
        max_length=50,
        blank=True,
    )

    due_at = models.DateTimeField(
        "期限",
        blank=True,
        null=True,
    )

    priority = models.CharField(
        "優先度",
        max_length=10,
        choices=Priority.choices,
        default=Priority.NORMAL,
    )

    is_completed = models.BooleanField(
        "完了",
        default=False,
    )

    note = models.TextField(
        "補足",
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="作成者",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_tasks",
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
        verbose_name = "お願い・ToDo"
        verbose_name_plural = "お願い・ToDo"
        ordering = ["is_completed", "due_at", "-created_at"]

    def __str__(self):
        return self.title


class BabyLog(models.Model):
    """赤ちゃんのミルク・睡眠・おむつなどを保存するモデル。"""

    class LogType(models.TextChoices):
        MILK = "milk", "ミルク"
        FOOD = "food", "離乳食"
        SLEEP = "sleep", "睡眠"
        DIAPER = "diaper", "おむつ"
        HEALTH = "health", "体調"
        GROWTH = "growth", "成長・行動"
        OTHER = "other", "その他"

    log_type = models.CharField(
        "記録の種類",
        max_length=20,
        choices=LogType.choices,
    )

    recorded_at = models.DateTimeField(
        "記録日時",
    )

    amount = models.DecimalField(
        "量",
        max_digits=7,
        decimal_places=1,
        blank=True,
        null=True,
    )

    unit = models.CharField(
        "単位",
        max_length=20,
        blank=True,
        help_text="例：ml、分、℃",
    )

    note = models.TextField(
        "メモ",
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="作成者",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_baby_logs",
    )

    created_at = models.DateTimeField(
        "作成日時",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "赤ちゃん記録"
        verbose_name_plural = "赤ちゃん記録"
        ordering = ["-recorded_at"]

    def __str__(self):
        return f"{self.get_log_type_display()} - {self.recorded_at:%Y-%m-%d %H:%M}"

class FamilyStatus(models.Model):
    """家族それぞれの現在の状態を保存するモデル。"""

    class Status(models.TextChoices):
        HOME = "home", "家にいる"
        MOVING = "moving", "移動中"
        SHOPPING = "shopping", "買い物中"
        RESTING = "resting", "休憩中"
        WITH_BABY = "with_baby", "赤ちゃんと一緒"
        SEPARATE = "separate", "別行動中"
        ARRIVED = "arrived", "目的地に到着"
        OTHER = "other", "その他"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="ユーザー",
        on_delete=models.CASCADE,
        related_name="family_status",
    )

    status = models.CharField(
        "現在の状態",
        max_length=20,
        choices=Status.choices,
        default=Status.HOME,
    )

    location_name = models.CharField(
        "現在地の名前",
        max_length=100,
        blank=True,
        help_text="例：実家、西宮北口、ホテル",
    )

    message = models.CharField(
        "ひとこと",
        max_length=150,
        blank=True,
    )

    updated_at = models.DateTimeField(
        "更新日時",
        auto_now=True,
    )

    class Meta:
        verbose_name = "家族の状態"
        verbose_name_plural = "家族の状態"
        ordering = ["user__username"]

    def __str__(self):
        return f"{self.user} - {self.get_status_display()}"

class MilkLog(models.Model):
    """赤ちゃんのミルク記録を保存するモデル。"""

    fed_at = models.DateTimeField(
        "授乳時刻",
    )

    amount_ml = models.PositiveIntegerField(
        "ミルク量（ml）",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="記録者",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_milk_logs",
    )

    created_at = models.DateTimeField(
        "作成日時",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "ミルク記録"
        verbose_name_plural = "ミルク記録"
        ordering = ["-fed_at"]

    def __str__(self):
        return f"{self.fed_at:%Y-%m-%d %H:%M} - {self.amount_ml} ml"

class SleepLog(models.Model):
    """赤ちゃんの睡眠記録を保存するモデル。"""

    started_at = models.DateTimeField(
        "寝入り時刻",
    )

    ended_at = models.DateTimeField(
        "起床時刻",
        blank=True,
        null=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="記録者",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_sleep_logs",
    )

    created_at = models.DateTimeField(
        "作成日時",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "睡眠記録"
        verbose_name_plural = "睡眠記録"
        ordering = ["-started_at"]

    @property
    def duration_minutes(self):
        """睡眠時間を分単位で返す。"""

        if self.ended_at is None:
            return None

        duration = self.ended_at - self.started_at

        return int(
            duration.total_seconds() // 60
        )

    def __str__(self):
        if self.ended_at is None:
            return (
                f"{self.started_at:%Y-%m-%d %H:%M}"
                "〜睡眠中"
            )

        return (
            f"{self.started_at:%Y-%m-%d %H:%M}"
            f"〜{self.ended_at:%H:%M}"
        )

class PoopLog(models.Model):
    """赤ちゃんのうんち記録を保存するモデル。"""

    class Amount(models.TextChoices):
        LARGE = "large", "多い"
        NORMAL = "normal", "ふつう"
        SMALL = "small", "少ない"

    happened_at = models.DateTimeField(
        "うんちの時刻",
    )

    amount = models.CharField(
        "うんちの量",
        max_length=10,
        choices=Amount.choices,
        default=Amount.NORMAL,
    )

    note = models.TextField(
        "メモ",
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="記録者",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_poop_logs",
    )

    created_at = models.DateTimeField(
        "作成日時",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "うんち記録"
        verbose_name_plural = "うんち記録"
        ordering = ["-happened_at"]

    def __str__(self):
        return (
            f"{self.happened_at:%Y-%m-%d %H:%M}"
            f" - {self.get_amount_display()}"
        )

class MeetingNote(models.Model):
    """家族会議の決定事項や次の行動を保存するモデル。"""

    title = models.CharField(
        "タイトル",
        max_length=200,
    )

    discussed_at = models.DateTimeField(
        "話し合った日時",
    )

    decisions = models.TextField(
        "決定事項",
    )

    next_actions = models.TextField(
        "次にやること",
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="記録者",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_meeting_notes",
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
        verbose_name = "家族会議メモ"
        verbose_name_plural = "家族会議メモ"
        ordering = ["-discussed_at"]

    def __str__(self):
        return self.title

class SharedLocation(models.Model):
    """家族が共有した現在地を保存するモデル。"""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="ユーザー",
        on_delete=models.CASCADE,
        related_name="shared_location",
    )

    latitude = models.DecimalField(
        "緯度",
        max_digits=9,
        decimal_places=6,
    )

    longitude = models.DecimalField(
        "経度",
        max_digits=9,
        decimal_places=6,
    )

    accuracy = models.PositiveIntegerField(
        "精度（m）",
        blank=True,
        null=True,
    )

    shared_at = models.DateTimeField(
        "共有日時",
        auto_now=True,
    )

    class Meta:
        verbose_name = "共有現在地"
        verbose_name_plural = "共有現在地"
        ordering = ["-shared_at"]

    def __str__(self):
        return f"{self.user} - {self.latitude}, {self.longitude}"

    @property
    def google_maps_url(self):
        return (
            "https://www.google.com/maps/search/"
            f"?api=1&query={self.latitude},{self.longitude}"
        )

class UserProfile(models.Model):
    """家族ユーザーのプロフィール情報を保存するモデル。"""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="ユーザー",
        on_delete=models.CASCADE,
        related_name="profile",
    )

    photo = models.ImageField(
        "プロフィール写真",
        upload_to="profile_photos/",
        blank=True,
        null=True,
    )

    updated_at = models.DateTimeField(
        "更新日時",
        auto_now=True,
    )

    class Meta:
        verbose_name = "家族プロフィール"
        verbose_name_plural = "家族プロフィール"

    def __str__(self):
        return f"{self.user} のプロフィール"

class ImportantNotice(models.Model):
    """ホーム画面に表示する重要なお知らせ。"""

    message = models.TextField(
        "お知らせ内容",
    )

    is_active = models.BooleanField(
        "表示する",
        default=True,
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="更新者",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="updated_notices",
    )

    updated_at = models.DateTimeField(
        "更新日時",
        auto_now=True,
    )

    class Meta:
        verbose_name = "重要なお知らせ"
        verbose_name_plural = "重要なお知らせ"
        ordering = [
            "-updated_at",
        ]

    def __str__(self):
        return self.message[:30]

class Expense(models.Model):
    """旅行中の支出を保存するモデル。"""

    class Category(models.TextChoices):
        FOOD = "food", "食事"
        TRANSPORT = "transport", "交通"
        SHOPPING = "shopping", "買い物"
        ACCOMMODATION = "accommodation", "宿泊"
        BABY = "baby", "赤ちゃん"
        OTHER = "other", "その他"

    class Currency(models.TextChoices):
        JPY = "JPY", "日本円"
        CHF = "CHF", "スイスフラン"
        CNY = "CNY", "中国元"
        EUR = "EUR", "ユーロ"

    title = models.CharField(
        "内容",
        max_length=100,
    )

    total_amount = models.DecimalField(
        "合計金額",
        max_digits=12,
        decimal_places=2,
        validators=[
            MinValueValidator(
                Decimal("0.01")
            ),
        ],
    )

    currency = models.CharField(
        "通貨",
        max_length=3,
        choices=Currency.choices,
        default=Currency.JPY,
    )

    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="支払った人",
        on_delete=models.PROTECT,
        related_name="paid_expenses",
    )

    paid_at = models.DateTimeField(
        "支払日時",
        default=timezone.now,
    )

    category = models.CharField(
        "カテゴリ",
        max_length=20,
        choices=Category.choices,
        default=Category.OTHER,
    )

    note = models.TextField(
        "メモ",
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="登録者",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_expenses",
    )

    created_at = models.DateTimeField(
        "登録日時",
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        "更新日時",
        auto_now=True,
    )

    class Meta:
        verbose_name = "支出"
        verbose_name_plural = "支出"
        ordering = [
            "-paid_at",
            "-id",
        ]

    def __str__(self):
        return (
            f"{self.title} "
            f"{self.total_amount} "
            f"{self.currency}"
        )


class ExpenseShare(models.Model):
    """支出1件に対する各ユーザーの負担額。"""

    expense = models.ForeignKey(
        Expense,
        verbose_name="支出",
        on_delete=models.CASCADE,
        related_name="shares",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="負担する人",
        on_delete=models.PROTECT,
        related_name="expense_shares",
    )

    amount = models.DecimalField(
        "負担額",
        max_digits=12,
        decimal_places=2,
        validators=[
            MinValueValidator(
                Decimal("0.00")
            ),
        ],
    )

    class Meta:
        verbose_name = "支出の負担額"
        verbose_name_plural = "支出の負担額"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "expense",
                    "user",
                ],
                name="unique_expense_share_user",
            ),
        ]

        ordering = [
            "user__username",
        ]

    def __str__(self):
        return (
            f"{self.expense.title}: "
            f"{self.user} "
            f"{self.amount} "
            f"{self.expense.currency}"
        )

class BabyGrowthNote(models.Model):
    """赤ちゃんの成長や変化についての気づきを記録する。"""

    observed_on = models.DateField(
        "記録日",
        default=timezone.localdate,
    )

    content = models.TextField(
        "記録内容",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="記録者",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="baby_growth_notes",
    )

    created_at = models.DateTimeField(
        "登録日時",
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        "更新日時",
        auto_now=True,
    )

    class Meta:
        verbose_name = "赤ちゃんの成長メモ"
        verbose_name_plural = "赤ちゃんの成長メモ"
        ordering = [
            "-observed_on",
            "-created_at",
        ]

    def __str__(self):
        return (
            f"{self.observed_on}: "
            f"{self.content[:30]}"
        )