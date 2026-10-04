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
    # Visibility / participant settings
    # =========================================================

    is_public = models.BooleanField(
        default=False,
    )

    allow_participant_date_addition = models.BooleanField(
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


        # -----------------------------------------------------
        # Fixed duration
        # -----------------------------------------------------

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


        # -----------------------------------------------------
        # NONE / VOTE では固定時間は使わない
        # -----------------------------------------------------

        if (
            self.duration_mode
            in [
                self.DurationMode.NONE,
                self.DurationMode.VOTE,
            ]
        ):

            self.duration_minutes = None


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