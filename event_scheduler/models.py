import uuid
from django.db.models import Q

from datetime import datetime, time

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from datetime import (
    datetime,
    time,
)


class AvailabilityStatus(models.TextChoices):

    YES = (
        "yes",
        "参加できる",
    )

    MAYBE = (
        "maybe",
        "未定",
    )

    NO = (
        "no",
        "参加できない",
    )

class Event(models.Model):

    # =========================================================
    # Scheduling mode
    # =========================================================

    class SchedulingMode(models.TextChoices):

        DATE_ONLY = (
            "date_only",
            "日付だけで決める",
        )

        TIME_OPTIONS = (
            "time_options",
            "時間帯から選ぶ",
        )

        START_TIMES = (
            "start_times",
            "開始時刻から選ぶ",
        )

        FREE_INPUT = (
            "free_input",
            "空き時間を入力してもらう",
        )


    # =========================================================
    # Duration mode
    # =========================================================

    class DurationMode(models.TextChoices):

        NONE = (
            "none",
            "指定しない",
        )

        FIXED = (
            "fixed",
            "作成者が決める",
        )

        VOTE = (
            "vote",
            "みんなで決める",
        )


    # =========================================================
    # Basic information
    # =========================================================

    title = models.CharField(
        max_length=200,
    )

    description = models.TextField(
        blank=True,
    )

    location = models.CharField(
        max_length=255,
        blank=True,
    )


    # =========================================================
    # Creator
    #
    # creator は「誰が作ったか」の記録。
    # 実際の管理権限は EventAdmin で管理する。
    # =========================================================

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_schedule_events",
    )


    # =========================================================
    # Guest share link
    # =========================================================

    share_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    # =========================================================
    # Visibility / participant settings
    # =========================================================

    is_public = models.BooleanField(
        default=False,
    )

    allow_participant_date_addition = models.BooleanField(
        default=False,
    )

    allow_participant_time_option_addition = models.BooleanField(
        default=False,
    )

    allow_participant_duration_addition = models.BooleanField(
        default=False,
    )


    # =========================================================
    # Scheduling
    # =========================================================

    scheduling_mode = models.CharField(
        max_length=30,
        choices=SchedulingMode.choices,
        default=SchedulingMode.DATE_ONLY,
    )


    # =========================================================
    # Duration
    # =========================================================

    duration_mode = models.CharField(
        max_length=20,
        choices=DurationMode.choices,
        default=DurationMode.FIXED,
    )

    duration_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
    )


    # =========================================================
    # Response deadline
    # =========================================================

    response_deadline = models.DateField(
        null=True,
        blank=True,
    )


    # =========================================================
    # Archive
    # =========================================================

    is_archived = models.BooleanField(
        default=False,
    )

    archived_at = models.DateTimeField(
        null=True,
        blank=True,
    )


    # =========================================================
    # Timestamps
    # =========================================================

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )


    # =========================================================
    # Meta
    # =========================================================

    class Meta:

        ordering = [
            "-created_at",
        ]


    # =========================================================
    # Validation
    # =========================================================

    def clean(self):

        super().clean()


        # =========================================================
        # Scheduling settings
        # =========================================================

        # ---------------------------------------------------------
        # TIME OPTIONS 以外では
        # 「時間帯追加」の設定は使わない
        # ---------------------------------------------------------

        if (
            self.scheduling_mode
            != self.SchedulingMode.TIME_OPTIONS
        ):

            self.allow_participant_time_option_addition = False


        # =========================================================
        # Duration settings
        # =========================================================

        # ---------------------------------------------------------
        # Fixed duration
        # ---------------------------------------------------------

        if (
            self.duration_mode
            == self.DurationMode.FIXED
            and
            not self.duration_minutes
        ):

            raise ValidationError(
                {
                    "duration_minutes":
                        (
                            "作成者がイベントの長さを決める場合は、"
                            "イベント時間を入力してください。"
                        )
                }
            )


        # ---------------------------------------------------------
        # NONE / VOTE では固定時間は使わない
        # ---------------------------------------------------------

        if (
            self.duration_mode
            in [
                self.DurationMode.NONE,
                self.DurationMode.VOTE,
            ]
        ):

            self.duration_minutes = None


        # ---------------------------------------------------------
        # VOTE 以外では参加者による長さ追加を使わない
        # ---------------------------------------------------------

        if (
            self.duration_mode
            != self.DurationMode.VOTE
        ):

            self.allow_participant_duration_addition = False

    # =========================================================
    # Permission
    # =========================================================

    def can_manage(
        self,
        user,
    ):

        if not user.is_authenticated:
            return False

        return self.admins.filter(
            user=user
        ).exists()


    # =========================================================
    # Response deadline datetime
    # =========================================================

    @property
    def response_deadline_at(self):

        if not self.response_deadline:
            return None


        deadline = datetime.combine(
            self.response_deadline,
            time.max,
        )


        if settings.USE_TZ:

            deadline = timezone.make_aware(
                deadline,
                timezone.get_current_timezone(),
            )


        return deadline


    # =========================================================
    # Automatic event icon
    # =========================================================

    @property
    def auto_icon(self):

        title = (
            self.title
            or ""
        ).lower()


        icon_rules = [

            # =================================================
            # Special events
            # =================================================

            (
                "🎂",
                [
                    "誕生日",
                    "birthday",
                    "geburtstag",
                ],
            ),

            (
                "🎄",
                [
                    "クリスマス",
                    "christmas",
                    "weihnacht",
                ],
            ),

            (
                "💍",
                [
                    "結婚式",
                    "結婚",
                    "wedding",
                    "hochzeit",
                ],
            ),

            (
                "🎃",
                [
                    "ハロウィン",
                    "halloween",
                ],
            ),


            # =================================================
            # Sports
            # =================================================

            (
                "🎾",
                [
                    "テニス",
                    "tennis",
                ],
            ),

            (
                "🏸",
                [
                    "バドミントン",
                    "badminton",
                ],
            ),

            (
                "🏓",
                [
                    "卓球",
                    "table tennis",
                    "ping pong",
                    "ping-pong",
                ],
            ),

            (
                "🏐",
                [
                    "バレーボール",
                    "バレー",
                    "volleyball",
                ],
            ),

            (
                "🏀",
                [
                    "バスケットボール",
                    "バスケ",
                    "basketball",
                ],
            ),

            (
                "⚽",
                [
                    "サッカー",
                    "フットサル",
                    "soccer",
                    "football",
                    "futsal",
                ],
            ),

            (
                "⚾",
                [
                    "野球",
                    "baseball",
                ],
            ),

            (
                "🏉",
                [
                    "ラグビー",
                    "rugby",
                ],
            ),

            (
                "🏈",
                [
                    "アメフト",
                    "american football",
                ],
            ),

            (
                "🏒",
                [
                    "アイスホッケー",
                    "ホッケー",
                    "ice hockey",
                    "hockey",
                ],
            ),

            (
                "🏊",
                [
                    "水泳",
                    "スイミング",
                    "泳ぐ",
                    "swimming",
                    "swim",
                ],
            ),

            (
                "🚴",
                [
                    "自転車",
                    "サイクリング",
                    "cycling",
                    "bicycle",
                    "bike ride",
                ],
            ),

            (
                "🏃",
                [
                    "ランニング",
                    "ジョギング",
                    "マラソン",
                    "running",
                    "jogging",
                    "marathon",
                ],
            ),

            (
                "🥾",
                [
                    "ハイキング",
                    "登山",
                    "トレッキング",
                    "hiking",
                    "trekking",
                    "wandern",
                ],
            ),

            (
                "🧗",
                [
                    "クライミング",
                    "ボルダリング",
                    "climbing",
                    "bouldering",
                ],
            ),

            (
                "⛷️",
                [
                    "スキー",
                    "skiing",
                    "ski",
                ],
            ),

            (
                "🏂",
                [
                    "スノーボード",
                    "スノボ",
                    "snowboarding",
                    "snowboard",
                ],
            ),

            (
                "⛸️",
                [
                    "アイススケート",
                    "スケート",
                    "ice skating",
                    "skating",
                ],
            ),

            (
                "🏌️",
                [
                    "ゴルフ",
                    "golf",
                ],
            ),

            (
                "🥊",
                [
                    "ボクシング",
                    "boxing",
                ],
            ),

            (
                "🥋",
                [
                    "柔道",
                    "空手",
                    "judo",
                    "karate",
                    "martial arts",
                ],
            ),

            (
                "🏋️",
                [
                    "筋トレ",
                    "ジム",
                    "トレーニング",
                    "フィットネス",
                    "gym",
                    "workout",
                    "fitness",
                ],
            ),

            (
                "🧘",
                [
                    "ヨガ",
                    "ピラティス",
                    "yoga",
                    "pilates",
                ],
            ),

            (
                "🏅",
                [
                    "スポーツ",
                    "sports",
                    "運動会",
                    "体育",
                ],
            ),


            # =================================================
            # Food / drink
            # =================================================

            (
                "🍖",
                [
                    "bbq",
                    "バーベキュー",
                    "焼肉",
                    "grill",
                ],
            ),

            (
                "🍕",
                [
                    "ピザ",
                    "pizza",
                ],
            ),

            (
                "🍣",
                [
                    "寿司",
                    "すし",
                    "sushi",
                ],
            ),

            (
                "🍻",
                [
                    "飲み会",
                    "ビール",
                    "beer",
                    "apéro",
                    "apero",
                ],
            ),

            (
                "☕",
                [
                    "カフェ",
                    "お茶",
                    "coffee",
                    "café",
                    "cafe",
                ],
            ),

            (
                "🍽️",
                [
                    "ランチ",
                    "ディナー",
                    "食事",
                    "ご飯",
                    "ごはん",
                    "lunch",
                    "dinner",
                    "brunch",
                    "restaurant",
                ],
            ),


            # =================================================
            # Travel / outdoor
            # =================================================

            (
                "🏖️",
                [
                    "海",
                    "ビーチ",
                    "beach",
                    "海水浴",
                ],
            ),

            (
                "🏕️",
                [
                    "キャンプ",
                    "camping",
                    "camp",
                ],
            ),

            (
                "✈️",
                [
                    "旅行",
                    "海外旅行",
                    "trip",
                    "travel",
                    "vacation",
                    "holiday",
                ],
            ),

            (
                "🚗",
                [
                    "ドライブ",
                    "drive",
                    "road trip",
                ],
            ),


            # =================================================
            # Entertainment
            # =================================================

            (
                "🎬",
                [
                    "映画",
                    "movie",
                    "cinema",
                    "kino",
                ],
            ),

            (
                "🎵",
                [
                    "コンサート",
                    "ライブ",
                    "音楽",
                    "concert",
                    "music",
                ],
            ),

            (
                "🎤",
                [
                    "カラオケ",
                    "karaoke",
                ],
            ),

            (
                "🎮",
                [
                    "ゲーム",
                    "game",
                    "gaming",
                ],
            ),

            (
                "🎲",
                [
                    "ボードゲーム",
                    "board game",
                    "ボドゲ",
                ],
            ),

            (
                "🎉",
                [
                    "パーティー",
                    "パーティ",
                    "party",
                    "お祝い",
                ],
            ),


            # =================================================
            # Study / work
            # =================================================

            (
                "📚",
                [
                    "勉強会",
                    "勉強",
                    "study",
                    "seminar",
                    "workshop",
                ],
            ),

            (
                "💻",
                [
                    "プログラミング",
                    "coding",
                    "programming",
                    "hackathon",
                    "ハッカソン",
                ],
            ),

            (
                "💼",
                [
                    "ミーティング",
                    "会議",
                    "打ち合わせ",
                    "meeting",
                ],
            ),


            # =================================================
            # Family / children
            # =================================================

            (
                "👶",
                [
                    "赤ちゃん",
                    "ベビー",
                    "baby",
                ],
            ),

            (
                "🧒",
                [
                    "子ども",
                    "子供",
                    "キッズ",
                    "kids",
                    "children",
                ],
            ),


            # =================================================
            # Shopping
            # =================================================

            (
                "🛍️",
                [
                    "買い物",
                    "ショッピング",
                    "shopping",
                ],
            ),
        ]


        for icon, keywords in icon_rules:

            if any(
                keyword in title
                for keyword in keywords
            ):

                return icon


        # -----------------------------------------------------
        # Default
        # -----------------------------------------------------

        return "📅"


    # =========================================================
    # String
    # =========================================================

    def __str__(self):

        return self.title

class EventAdmin(models.Model):

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="admins",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="admin_schedule_events",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "event",
                    "user",
                ],
                name="unique_event_admin",
            ),
        ]


    def __str__(self):

        return (
            f"{self.event} - "
            f"{self.user}"
        )

# =========================================================
# Event admin invitation
# =========================================================

class EventAdminInvitation(models.Model):

    class Status(models.TextChoices):

        PENDING = (
            "pending",
            "招待中",
        )

        ACCEPTED = (
            "accepted",
            "承認済み",
        )

        DECLINED = (
            "declined",
            "辞退",
        )


    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="admin_invitations",
    )

    invited_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="event_admin_invitations",
    )

    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_event_admin_invitations",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )


    class Meta:

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "event",
                    "invited_user",
                ],
                name="unique_event_admin_invitation",
            ),
        ]

        ordering = [
            "-created_at",
        ]


    def __str__(self):

        return (
            f"{self.event.title} - "
            f"{self.invited_user} - "
            f"{self.status}"
        )

class EventParticipant(models.Model):

    class Status(models.TextChoices):

        INVITED = (
            "invited",
            "招待中",
        )

        JOINED = (
            "joined",
            "参加",
        )

        DECLINED = (
            "declined",
            "不参加",
        )


    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="participants",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="schedule_events",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.INVITED,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "event",
                    "user",
                ],
                name="unique_event_participant",
            ),
        ]

    def __str__(self):

        return (
            f"{self.event} - "
            f"{self.user} - "
            f"{self.status}"
        )

# =========================================================
# Guest participants
# =========================================================

class EventGuestParticipant(models.Model):

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="guest_participants",
    )

    display_name = models.CharField(
        max_length=50,
    )

    edit_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "created_at",
            "id",
        ]

    def __str__(self):
        return (
            f"{self.event.title} - "
            f"{self.display_name}"
        )

# =========================================================
# Event duration
# =========================================================

class EventDurationOption(models.Model):

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="duration_options",
    )

    minutes = models.PositiveIntegerField()

    order = models.PositiveIntegerField(
        default=0,
    )

    class Meta:

        ordering = [
            "order",
            "minutes",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "event",
                    "minutes",
                ],
                name="unique_event_duration_option",
            ),
        ]

    @property
    def display_label(self):

        hours, minutes = divmod(
            self.minutes,
            60,
        )

        if hours and minutes:

            return (
                f"{hours}時間"
                f"{minutes}分"
            )

        if hours:

            return (
                f"{hours}時間"
            )

        return (
            f"{minutes}分"
        )

    def __str__(self):

        return (
            f"{self.event.title} - "
            f"{self.display_label}"
        )


class EventDurationVote(models.Model):

    duration_option = models.ForeignKey(
        EventDurationOption,
        on_delete=models.CASCADE,
        related_name="votes",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="event_duration_votes",
        null=True,
        blank=True,
    )

    guest = models.ForeignKey(
        EventGuestParticipant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="duration_votes",
    )


    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        constraints = [

            models.UniqueConstraint(
                fields=[
                    "duration_option",
                    "user",
                ],
                name="unique_event_duration_vote",
            ),

            models.UniqueConstraint(
                fields=[
                    "duration_option",
                    "guest",
                ],
                name="unique_guest_duration_vote",
            ),

            models.CheckConstraint(
                condition=(
                    Q(user__isnull=False, guest__isnull=True)
                    | Q(user__isnull=True, guest__isnull=False)
                ),
                name="event_duration_vote_one_owner",
            ),

        ]

    def __str__(self):

        return (
            f"{self.duration_option} - "
            f"{self.user}"
        )

# =========================================================
# Candidate dates
# =========================================================

class EventDate(models.Model):

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="candidate_dates",
    )

    date = models.DateField()

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_event_dates",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:

        ordering = [
            "date",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "event",
                    "date",
                ],
                name="unique_event_candidate_date",
            ),
        ]

    def __str__(self):

        return (
            f"{self.event.title} - "
            f"{self.date}"
        )


# =========================================================
# Mode 1
# Date only
# =========================================================

class EventDateVote(models.Model):

    event_date = models.ForeignKey(
        EventDate,
        on_delete=models.CASCADE,
        related_name="date_votes",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="event_date_votes",
        null=True,
        blank=True,
    )

    guest = models.ForeignKey(
        EventGuestParticipant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="date_votes",
    )

    status = models.CharField(
        max_length=20,
        choices=AvailabilityStatus.choices,
    )

    note = models.CharField(
        max_length=255,
        blank=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        constraints = [

            models.UniqueConstraint(
                fields=[
                    "event_date",
                    "user",
                ],
                name="unique_event_date_vote",
            ),

            models.UniqueConstraint(
                fields=[
                    "event_date",
                    "guest",
                ],
                name="unique_guest_event_date_vote",
            ),

            models.CheckConstraint(
                condition=(
                    Q(user__isnull=False, guest__isnull=True)
                    | Q(user__isnull=True, guest__isnull=False)
                ),
                name="event_date_vote_one_owner",
            ),

        ]

# =========================================================
# Mode 2
# Time options
#
# 例:
# 午前
# 午後
# 夕方
#
# 時刻の定義は任意
# =========================================================

class EventTimeOption(models.Model):

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="time_options",
    )

    label = models.CharField(
        max_length=100,
    )

    start_time = models.TimeField(
        null=True,
        blank=True,
    )

    end_time = models.TimeField(
        null=True,
        blank=True,
    )

    order = models.PositiveIntegerField(
        default=0,
    )

    class Meta:
        ordering = [
            "order",
            "id",
        ]

    def clean(self):

        if bool(self.start_time) != bool(self.end_time):

            raise ValidationError(
                "開始時刻と終了時刻は両方入力するか、"
                "両方空欄にしてください。"
            )

        if (
            self.start_time
            and
            self.end_time
            and
            self.end_time <= self.start_time
        ):

            raise ValidationError(
                {
                    "end_time":
                        "終了時刻は開始時刻より後にしてください。"
                }
            )

    def __str__(self):
        return self.label


class EventTimeOptionVote(models.Model):

    event_date = models.ForeignKey(
        EventDate,
        on_delete=models.CASCADE,
        related_name="time_option_votes",
    )

    time_option = models.ForeignKey(
        EventTimeOption,
        on_delete=models.CASCADE,
        related_name="votes",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="event_time_option_votes",
        null=True,
        blank=True,
    )

    guest = models.ForeignKey(
        EventGuestParticipant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="time_option_votes",
    )

    status = models.CharField(
        max_length=20,
        choices=AvailabilityStatus.choices,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        constraints = [

            models.UniqueConstraint(
                fields=[
                    "event_date",
                    "time_option",
                    "user",
                ],
                name="unique_event_time_option_vote",
            ),

            models.UniqueConstraint(
                fields=[
                    "event_date",
                    "time_option",
                    "guest",
                ],
                name="unique_guest_time_option_vote",
            ),

            models.CheckConstraint(
                condition=(
                    Q(user__isnull=False, guest__isnull=True)
                    | Q(user__isnull=True, guest__isnull=False)
                ),
                name="event_time_vote_one_owner",
            ),

        ]

# =========================================================
# Mode 3
# Start times
#
# 例:
# 10月20日 18:00
# 10月20日 18:30
# 10月21日 19:00
# =========================================================

class EventStartTimeOption(models.Model):

    event_date = models.ForeignKey(
        EventDate,
        on_delete=models.CASCADE,
        related_name="start_time_options",
    )

    start_time = models.TimeField()

    order = models.PositiveIntegerField(
        default=0,
    )

    class Meta:

        ordering = [
            "order",
            "start_time",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "event_date",
                    "start_time",
                ],
                name="unique_event_start_time_option",
            ),
        ]

    def __str__(self):

        return (
            f"{self.event_date.date} "
            f"{self.start_time}"
        )


class EventStartTimeVote(models.Model):

    start_time_option = models.ForeignKey(
        EventStartTimeOption,
        on_delete=models.CASCADE,
        related_name="votes",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="event_start_time_votes",
        null=True,
        blank=True,
    )

    guest = models.ForeignKey(
        EventGuestParticipant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="start_time_votes",
    )


    status = models.CharField(
        max_length=20,
        choices=AvailabilityStatus.choices,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        constraints = [

            models.UniqueConstraint(
                fields=[
                    "start_time_option",
                    "user",
                ],
                name="unique_event_start_time_vote",
            ),

            models.UniqueConstraint(
                fields=[
                    "start_time_option",
                    "guest",
                ],
                name="unique_guest_start_time_vote",
            ),

            models.CheckConstraint(
                condition=(
                    Q(user__isnull=False, guest__isnull=True)
                    | Q(user__isnull=True, guest__isnull=False)
                ),
                name="event_start_time_vote_one_owner",
            ),

        ]

# =========================================================
# Mode 4
# Free input
# =========================================================

class EventDateResponse(models.Model):

    class ResponseType(models.TextChoices):

        UNAVAILABLE = (
            "unavailable",
            "参加できない",
        )

        ALL_DAY = (
            "all_day",
            "終日OK",
        )

        PARTIAL = (
            "partial",
            "時間を指定",
        )


    event_date = models.ForeignKey(
        EventDate,
        on_delete=models.CASCADE,
        related_name="free_input_responses",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="event_date_responses",
        null=True,
        blank=True,
    )

    guest = models.ForeignKey(
        EventGuestParticipant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="date_responses",
    )


    response_type = models.CharField(
        max_length=20,
        choices=ResponseType.choices,
    )

    note = models.CharField(
        max_length=255,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        constraints = [

            models.UniqueConstraint(
                fields=[
                    "event_date",
                    "user",
                ],
                name="unique_event_date_response",
            ),

            models.UniqueConstraint(
                fields=[
                    "event_date",
                    "guest",
                ],
                name="unique_guest_date_response",
            ),

            models.CheckConstraint(
                condition=(
                    Q(user__isnull=False, guest__isnull=True)
                    | Q(user__isnull=True, guest__isnull=False)
                ),
                name="event_date_response_one_owner",
            ),

        ]

    def __str__(self):

        return (
            f"{self.event_date} - "
            f"{self.user}"
        )


class AvailabilityWindow(models.Model):

    response = models.ForeignKey(
        EventDateResponse,
        on_delete=models.CASCADE,
        related_name="windows",
    )

    start_time = models.TimeField()

    end_time = models.TimeField()

    class Meta:
        ordering = [
            "start_time",
        ]

    def clean(self):

        if self.end_time <= self.start_time:

            raise ValidationError(
                {
                    "end_time":
                        "終了時刻は開始時刻より後にしてください。"
                }
            )

    def __str__(self):

        return (
            f"{self.start_time} - "
            f"{self.end_time}"
        )


# =========================================================
# Comments
# =========================================================

class EventComment(models.Model):

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="comments",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="event_comments",
    )

    body = models.TextField()

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "created_at",
        ]

    def __str__(self):

        return (
            f"{self.event} - "
            f"{self.user}"
        )