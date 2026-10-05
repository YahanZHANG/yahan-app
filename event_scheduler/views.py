from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Max

from django.db import transaction
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.utils.dateparse import (
    parse_date,
    parse_time,
)

from .forms import (
    EventAdminInviteForm,
    EventDateForm,
    EventForm,
)

from .models import (
    AvailabilityStatus,
    AvailabilityWindow,
    Event,
    EventAdmin,
    EventAdminInvitation,
    EventDate,
    EventDateResponse,
    EventDateVote,
    EventDurationOption,
    EventDurationVote,
    EventParticipant,
    EventStartTimeOption,
    EventStartTimeVote,
    EventTimeOption,
    EventTimeOptionVote,
)


# =========================================================
# Event list
# =========================================================

@login_required
def event_list(request):

    events = (
        Event.objects
        .filter(
            participants__user=request.user,
            is_archived=False,
        )
        .distinct()
    )

    public_events = (
        Event.objects
        .filter(
            is_public=True,
            is_archived=False,
        )
        .exclude(
            participants__user=request.user,
        )
        .distinct()
    )

    pending_admin_invitations = (
        EventAdminInvitation.objects
        .filter(
            invited_user=request.user,
            status=EventAdminInvitation.Status.PENDING,
        )
        .select_related(
            "event",
            "invited_by",
        )
        .order_by(
            "-created_at",
        )
    )

    return render(
        request,
        "event_scheduler/event_list.html",
        {
            "events": events,
            "public_events": public_events,
            "pending_admin_invitations":pending_admin_invitations,
        },
    )

# =========================================================
# Archived event list
# =========================================================

@login_required
def archived_event_list(request):

    events = (
        Event.objects
        .filter(
            participants__user=request.user,
            is_archived=True,
        )
        .distinct()
        .order_by(
            "-archived_at",
            "-updated_at",
        )
    )


    event_rows = []


    for event in events:

        event_rows.append(
            {
                "event":
                    event,

                "can_manage":
                    event.can_manage(
                        request.user
                    ),
            }
        )


    return render(
        request,
        "event_scheduler/event_archived_list.html",
        {
            "event_rows":
                event_rows,
        },
    )

# =========================================================
# Create event
# =========================================================

@login_required
def event_create(request):

    # -----------------------------------------------------
    # Keep entered values when validation fails
    # -----------------------------------------------------

    posted_candidate_dates = []
    posted_time_options = []
    posted_start_times = []
    posted_duration_options = []


    if request.method == "POST":

        form = EventForm(
            request.POST,
        )

        # Django標準のvalidationを先に実行
        form.is_valid()


        # =================================================
        # Keep posted values
        # =================================================

        posted_candidate_dates = (
            request.POST.getlist(
                "candidate_date"
            )
        )


        posted_labels = (
            request.POST.getlist(
                "time_option_label"
            )
        )

        posted_starts = (
            request.POST.getlist(
                "time_option_start"
            )
        )

        posted_ends = (
            request.POST.getlist(
                "time_option_end"
            )
        )

        for label, start, end in zip(
            posted_labels,
            posted_starts,
            posted_ends,
        ):

            posted_time_options.append(
                {
                    "label": label,
                    "start": start,
                    "end": end,
                }
            )


        posted_start_dates = (
            request.POST.getlist(
                "start_time_date"
            )
        )

        posted_start_values = (
            request.POST.getlist(
                "start_time_value"
            )
        )

        for date_value, time_value in zip(
            posted_start_dates,
            posted_start_values,
        ):

            posted_start_times.append(
                {
                    "date": date_value,
                    "time": time_value,
                }
            )


        # =================================================
        # Duration options
        # =================================================

        raw_duration_options = (
            request.POST.getlist(
                "duration_option_minutes"
            )
        )

        duration_options = []


        for raw_minutes in raw_duration_options:

            raw_minutes = (
                raw_minutes.strip()
            )

            if not raw_minutes:
                continue


            # エラー時に画面へ戻すため、
            # 入力値自体は保持する
            posted_duration_options.append(
                raw_minutes
            )


            try:

                minutes = int(
                    raw_minutes
                )

            except ValueError:

                form.add_error(
                    None,
                    (
                        "イベント時間は"
                        "数字で入力してください。"
                    ),
                )

                continue


            if minutes <= 0:

                form.add_error(
                    None,
                    (
                        "イベント時間は"
                        "1分以上にしてください。"
                    ),
                )

                continue


            if minutes not in duration_options:

                duration_options.append(
                    minutes
                )


        duration_mode = (
            request.POST.get(
                "duration_mode"
            )
        )


        if (
            duration_mode
            == Event.DurationMode.VOTE
            and
            len(duration_options) < 2
        ):

            form.add_error(
                None,
                (
                    "みんなでイベントの長さを決める場合は、"
                    "2つ以上の候補を設定してください。"
                ),
            )


        # =================================================
        # Candidate dates
        # =================================================

        raw_candidate_dates = (
            request.POST.getlist(
                "candidate_date"
            )
        )

        candidate_dates = []


        for raw_date in raw_candidate_dates:

            if not raw_date:
                continue

            parsed_date = parse_date(
                raw_date
            )

            if (
                parsed_date
                and
                parsed_date not in candidate_dates
            ):

                candidate_dates.append(
                    parsed_date
                )


        if not candidate_dates:

            form.add_error(
                None,
                "候補日を1つ以上追加してください。",
            )


        # =================================================
        # Scheduling mode
        # =================================================

        scheduling_mode = (
            request.POST.get(
                "scheduling_mode"
            )
        )


        # =================================================
        # Mode 2:
        # Time options
        #
        # 例:
        # 午前 / 午後 / 夕方
        # =================================================

        time_options = []


        if (
            scheduling_mode
            == Event.SchedulingMode.TIME_OPTIONS
        ):

            labels = (
                request.POST.getlist(
                    "time_option_label"
                )
            )

            starts = (
                request.POST.getlist(
                    "time_option_start"
                )
            )

            ends = (
                request.POST.getlist(
                    "time_option_end"
                )
            )


            for label, start, end in zip(
                labels,
                starts,
                ends,
            ):

                label = label.strip()
                start = start.strip()
                end = end.strip()


                if not label:
                    continue


                start_time = (
                    parse_time(start)
                    if start
                    else None
                )

                end_time = (
                    parse_time(end)
                    if end
                    else None
                )


                # -----------------------------------------
                # Invalid time format
                # -----------------------------------------

                if (
                    start
                    and
                    start_time is None
                ):

                    form.add_error(
                        None,
                        (
                            f"「{label}」の開始時刻を"
                            "HH:MM形式で入力してください。"
                        ),
                    )

                    continue


                if (
                    end
                    and
                    end_time is None
                ):

                    form.add_error(
                        None,
                        (
                            f"「{label}」の終了時刻を"
                            "HH:MM形式で入力してください。"
                        ),
                    )

                    continue


                # -----------------------------------------
                # One side only
                # -----------------------------------------

                if bool(start_time) != bool(end_time):

                    form.add_error(
                        None,
                        (
                            f"「{label}」の開始時刻と"
                            "終了時刻は両方入力するか、"
                            "両方空欄にしてください。"
                        ),
                    )

                    continue


                # -----------------------------------------
                # Within one option,
                # end must be after start
                #
                # 別の選択肢との重複はOK
                # -----------------------------------------

                if (
                    start_time
                    and
                    end_time
                    and
                    end_time <= start_time
                ):

                    form.add_error(
                        None,
                        (
                            f"「{label}」の終了時刻は"
                            "開始時刻より後にしてください。"
                        ),
                    )

                    continue


                time_options.append(
                    {
                        "label": label,
                        "start_time": start_time,
                        "end_time": end_time,
                    }
                )


            if not time_options:

                form.add_error(
                    None,
                    (
                        "時間帯から選ぶ場合は、"
                        "選択肢を1つ以上追加してください。"
                    ),
                )


        # =================================================
        # Mode 3:
        # Start time options
        # =================================================

        start_time_options = []


        if (
            scheduling_mode
            == Event.SchedulingMode.START_TIMES
        ):

            raw_start_dates = (
                request.POST.getlist(
                    "start_time_date"
                )
            )

            raw_start_times = (
                request.POST.getlist(
                    "start_time_value"
                )
            )


            for raw_date, raw_time in zip(
                raw_start_dates,
                raw_start_times,
            ):

                raw_date = raw_date.strip()
                raw_time = raw_time.strip()


                if (
                    not raw_date
                    or
                    not raw_time
                ):

                    continue


                parsed_date = parse_date(
                    raw_date
                )

                parsed_time = parse_time(
                    raw_time
                )


                if parsed_date is None:

                    continue


                if parsed_time is None:

                    form.add_error(
                        None,
                        (
                            f"{raw_date} の開始時刻を"
                            "HH:MM形式で入力してください。"
                        ),
                    )

                    continue


                item = (
                    parsed_date,
                    parsed_time,
                )


                if item not in start_time_options:

                    start_time_options.append(
                        item
                    )


            # すべての候補日に
            # 少なくとも1つ開始時刻が必要
            for candidate_date in candidate_dates:

                has_time = any(
                    item_date == candidate_date
                    for item_date, item_time
                    in start_time_options
                )


                if not has_time:

                    form.add_error(
                        None,
                        (
                            f"{candidate_date.strftime('%Y/%m/%d')} "
                            "の開始時間を1つ以上"
                            "設定してください。"
                        ),
                    )


        # =================================================
        # Save
        # =================================================

        if form.is_valid():

            with transaction.atomic():

                event = form.save(
                    commit=False,
                )

                event.creator = (
                    request.user
                )


                # 固定以外では、
                # duration_minutes は使用しない
                if (
                    event.duration_mode
                    != Event.DurationMode.FIXED
                ):

                    event.duration_minutes = None


                event.save()


                # -----------------------------------------
                # Duration options
                # -----------------------------------------

                if (
                    event.duration_mode
                    == Event.DurationMode.VOTE
                ):

                    for index, minutes in enumerate(
                        duration_options
                    ):

                        EventDurationOption.objects.create(
                            event=event,
                            minutes=minutes,
                            order=index,
                        )


                # -----------------------------------------
                # Creator = admin
                # -----------------------------------------

                EventAdmin.objects.get_or_create(
                    event=event,
                    user=request.user,
                )


                # -----------------------------------------
                # Creator = participant
                # -----------------------------------------

                EventParticipant.objects.get_or_create(
                    event=event,
                    user=request.user,
                    defaults={
                        "status":
                            EventParticipant.Status.JOINED,
                    },
                )


                # -----------------------------------------
                # Candidate dates
                # -----------------------------------------

                event_date_map = {}


                for candidate_date in candidate_dates:

                    event_date = (
                        EventDate.objects.create(
                            event=event,
                            date=candidate_date,
                            created_by=request.user,
                        )
                    )

                    event_date_map[
                        candidate_date
                    ] = event_date


                # -----------------------------------------
                # Mode 2:
                # Time options
                # -----------------------------------------

                if (
                    event.scheduling_mode
                    == Event.SchedulingMode.TIME_OPTIONS
                ):

                    for index, option in enumerate(
                        time_options
                    ):

                        EventTimeOption.objects.create(
                            event=event,
                            label=option["label"],
                            start_time=(
                                option["start_time"]
                            ),
                            end_time=(
                                option["end_time"]
                            ),
                            order=index,
                        )


                # -----------------------------------------
                # Mode 3:
                # Start time options
                # -----------------------------------------

                if (
                    event.scheduling_mode
                    == Event.SchedulingMode.START_TIMES
                ):

                    order_counter = {}


                    for (
                        option_date,
                        option_time,
                    ) in start_time_options:

                        event_date = (
                            event_date_map.get(
                                option_date
                            )
                        )


                        if not event_date:
                            continue


                        current_order = (
                            order_counter.get(
                                option_date,
                                0,
                            )
                        )


                        EventStartTimeOption.objects.create(
                            event_date=event_date,
                            start_time=option_time,
                            order=current_order,
                        )


                        order_counter[
                            option_date
                        ] = (
                            current_order + 1
                        )


            return redirect(
                "event_scheduler:event_detail",
                event_id=event.id,
            )


    else:

        form = EventForm()


    return render(
        request,
        "event_scheduler/event_form.html",
        {
            "form":
                form,

            "posted_candidate_dates":
                posted_candidate_dates,

            "posted_time_options":
                posted_time_options,

            "posted_start_times":
                posted_start_times,

            "posted_duration_options":
                posted_duration_options,
        },
    )


# =========================================================
# Event detail
# =========================================================

@login_required
def event_detail(
    request,
    event_id,
):

    event = get_object_or_404(
        Event,
        id=event_id,
    )


    participant = (
        EventParticipant.objects
        .filter(
            event=event,
            user=request.user,
        )
        .first()
    )


    can_manage = event.can_manage(
        request.user
    )


    # =========================================================
    # Access check
    # =========================================================

    if (
        not event.is_public
        and
        participant is None
        and
        not can_manage
    ):

        return redirect(
            "event_scheduler:event_list"
        )


    candidate_dates = list(
        event.candidate_dates
        .all()
        .order_by(
            "date",
            "id",
        )
    )


    # =========================================================
    # Has current user answered?
    # =========================================================

    has_answered = False


    if (
        event.scheduling_mode
        == Event.SchedulingMode.DATE_ONLY
    ):

        has_answered = (
            EventDateVote.objects
            .filter(
                event_date__event=event,
                user=request.user,
            )
            .exists()
        )


    elif (
        event.scheduling_mode
        == Event.SchedulingMode.TIME_OPTIONS
    ):

        has_answered = (
            EventTimeOptionVote.objects
            .filter(
                event_date__event=event,
                user=request.user,
            )
            .exists()
        )


    elif (
        event.scheduling_mode
        == Event.SchedulingMode.START_TIMES
    ):

        has_answered = (
            EventStartTimeVote.objects
            .filter(
                start_time_option__event_date__event=event,
                user=request.user,
            )
            .exists()
        )


    elif (
        event.scheduling_mode
        == Event.SchedulingMode.FREE_INPUT
    ):

        has_answered = (
            EventDateResponse.objects
            .filter(
                event_date__event=event,
                user=request.user,
            )
            .exists()
        )


    # =========================================================
    # Result data
    # =========================================================

    result_rows = []

    best_result = None

    duration_result_rows = []

    best_duration = None


    def get_vote_counts(
        queryset,
    ):

        return {
            "yes":
                queryset.filter(
                    status="yes",
                ).count(),

            "maybe":
                queryset.filter(
                    status="maybe",
                ).count(),

            "no":
                queryset.filter(
                    status="no",
                ).count(),
        }


    # =========================================================
    # Show results only after this user has answered
    # =========================================================

    if has_answered:

        # -----------------------------------------------------
        # Date only
        # -----------------------------------------------------

        if (
            event.scheduling_mode
            == Event.SchedulingMode.DATE_ONLY
        ):

            for candidate in candidate_dates:

                counts = get_vote_counts(
                    EventDateVote.objects.filter(
                        event_date=candidate,
                    )
                )


                result_rows.append(
                    {
                        "date":
                            candidate.date,

                        "label":
                            "",

                        "start_time":
                            None,

                        "end_time":
                            None,

                        "yes_count":
                            counts["yes"],

                        "maybe_count":
                            counts["maybe"],

                        "no_count":
                            counts["no"],
                    }
                )


        # -----------------------------------------------------
        # Time options
        # -----------------------------------------------------

        elif (
            event.scheduling_mode
            == Event.SchedulingMode.TIME_OPTIONS
        ):

            time_options = list(
                event.time_options.all()
            )


            for candidate in candidate_dates:

                for option in time_options:

                    counts = get_vote_counts(
                        EventTimeOptionVote.objects.filter(
                            event_date=candidate,
                            time_option=option,
                        )
                    )


                    result_rows.append(
                        {
                            "date":
                                candidate.date,

                            "label":
                                option.label,

                            "start_time":
                                option.start_time,

                            "end_time":
                                option.end_time,

                            "yes_count":
                                counts["yes"],

                            "maybe_count":
                                counts["maybe"],

                            "no_count":
                                counts["no"],
                        }
                    )


        # -----------------------------------------------------
        # Start times
        # -----------------------------------------------------

        elif (
            event.scheduling_mode
            == Event.SchedulingMode.START_TIMES
        ):

            start_options = (
                EventStartTimeOption.objects
                .filter(
                    event_date__event=event,
                )
                .select_related(
                    "event_date",
                )
                .order_by(
                    "event_date__date",
                    "order",
                    "id",
                )
            )


            for option in start_options:

                counts = get_vote_counts(
                    EventStartTimeVote.objects.filter(
                        start_time_option=option,
                    )
                )


                result_rows.append(
                    {
                        "date":
                            option.event_date.date,

                        "label":
                            "",

                        "start_time":
                            option.start_time,

                        "end_time":
                            None,

                        "yes_count":
                            counts["yes"],

                        "maybe_count":
                            counts["maybe"],

                        "no_count":
                            counts["no"],
                    }
                )


        # -----------------------------------------------------
        # Free input
        # -----------------------------------------------------

        elif (
            event.scheduling_mode
            == Event.SchedulingMode.FREE_INPUT
        ):

            for candidate in candidate_dates:

                responses = (
                    EventDateResponse.objects
                    .filter(
                        event_date=candidate,
                    )
                )


                result_rows.append(
                    {
                        "date":
                            candidate.date,

                        "label":
                            "",

                        "start_time":
                            None,

                        "end_time":
                            None,

                        "yes_count":
                            responses.filter(
                                response_type="all_day",
                            ).count(),

                        "maybe_count":
                            responses.filter(
                                response_type="partial",
                            ).count(),

                        "no_count":
                            responses.filter(
                                response_type="unavailable",
                            ).count(),
                    }
                )


        # =====================================================
        # Best candidate
        # =====================================================

        answered_result_rows = [
            row
            for row in result_rows
            if (
                row["yes_count"]
                +
                row["maybe_count"]
                +
                row["no_count"]
            ) > 0
        ]


        if answered_result_rows:

            best_result = max(
                answered_result_rows,
                key=lambda row: (
                    row["yes_count"],
                    row["maybe_count"],
                    -row["no_count"],
                ),
            )


        # =====================================================
        # Duration results
        # =====================================================

        if (
            event.duration_mode
            == Event.DurationMode.VOTE
        ):

            for option in (
                event.duration_options
                .all()
                .order_by(
                    "order",
                    "id",
                )
            ):

                vote_count = (
                    EventDurationVote.objects
                    .filter(
                        duration_option=option,
                    )
                    .count()
                )


                duration_result_rows.append(
                    {
                        "option":
                            option,

                        "vote_count":
                            vote_count,
                    }
                )


            if duration_result_rows:

                possible_best_duration = max(
                    duration_result_rows,
                    key=lambda row:
                        row["vote_count"],
                )


                if (
                    possible_best_duration[
                        "vote_count"
                    ]
                    > 0
                ):

                    best_duration = (
                        possible_best_duration
                    )


    # =========================================================
    # Admin
    # =========================================================

    admin_count = (
        EventAdmin.objects
        .filter(
            event=event,
        )
        .count()
    )


    # =========================================================
    # Render
    # =========================================================

    return render(
        request,
        "event_scheduler/event_detail.html",
        {
            "event":
                event,

            "participant":
                participant,

            "can_manage":
                can_manage,

            "admin_count":
                admin_count,

            "has_answered":
                has_answered,

            "result_rows":
                result_rows,

            "best_result":
                best_result,

            "duration_result_rows":
                duration_result_rows,

            "best_duration":
                best_duration,
        },
    )

# =========================================================
# Add candidate date
# =========================================================

@login_required
def event_date_add(
    request,
    event_id,
):

    event = get_object_or_404(
        Event,
        id=event_id,
    )


    can_manage = event.can_manage(
        request.user
    )


    participant = (
        EventParticipant.objects
        .filter(
            event=event,
            user=request.user,
            status=EventParticipant.Status.JOINED,
        )
        .exists()
    )


    if not can_manage:

        if not (
            participant
            and
            event.allow_participant_date_addition
        ):

            return redirect(
                "event_scheduler:event_detail",
                event_id=event.id,
            )


    if request.method == "POST":

        form = EventDateForm(
            request.POST,
        )


        if form.is_valid():

            event_date = form.save(
                commit=False,
            )

            event_date.event = event

            event_date.created_by = (
                request.user
            )


            # 同じ候補日の重複を避ける
            if (
                EventDate.objects
                .filter(
                    event=event,
                    date=event_date.date,
                )
                .exists()
            ):

                form.add_error(
                    "date",
                    "この日はすでに候補日に入っています。",
                )

            else:

                event_date.save()


                return redirect(
                    "event_scheduler:event_detail",
                    event_id=event.id,
                )


    else:

        form = EventDateForm()


    return render(
        request,
        "event_scheduler/event_date_form.html",
        {
            "event": event,
            "form": form,
        },
    )


# =========================================================
# Join public event
# =========================================================

@login_required
def join_event(
    request,
    event_id,
):

    event = get_object_or_404(
        Event,
        id=event_id,
        is_public=True,
    )


    if request.method == "POST":

        participant, created = (
            EventParticipant.objects
            .get_or_create(
                event=event,
                user=request.user,
            )
        )


        participant.status = (
            EventParticipant.Status.JOINED
        )

        participant.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )


    return redirect(
        "event_scheduler:event_detail",
        event_id=event.id,
    )


# =========================================================
# Respond to event
# =========================================================

@login_required
def event_respond(
    request,
    event_id,
):

    event = get_object_or_404(
        Event,
        id=event_id,
    )


    participant = (
        EventParticipant.objects
        .filter(
            event=event,
            user=request.user,
            status=EventParticipant.Status.JOINED,
        )
        .first()
    )


    if participant is None:

        return redirect(
            "event_scheduler:event_detail",
            event_id=event.id,
        )


    can_manage = event.can_manage(
        request.user
    )


    can_add_date = (
        can_manage
        or
        event.allow_participant_date_addition
    )


    can_add_duration = (
        event.duration_mode
        == Event.DurationMode.VOTE
        and
        (
            can_manage
            or
            event.allow_participant_duration_addition
        )
    )


    errors = []


    new_candidate_date_value = ""

    new_candidate_start_time_value = ""

    new_duration_minutes_value = ""


    # =========================================================
    # Which button was pressed?
    # =========================================================

    action = ""


    if request.method == "POST":

        if (
            "add_candidate_date"
            in request.POST
        ):

            action = "add_candidate_date"


        elif (
            "add_duration_option"
            in request.POST
        ):

            action = "add_duration_option"


        else:

            action = "save_response"


    # =========================================================
    # Time helper
    # 0930 -> 09:30
    # =========================================================

    def normalize_time_input(
        value,
    ):

        value = (
            value
            or ""
        ).strip()


        if (
            len(value) == 4
            and
            value.isdigit()
        ):

            value = (
                value[:2]
                +
                ":"
                +
                value[2:]
            )


        return value


    # =========================================================
    # Candidate dates
    # =========================================================

    candidate_dates = list(
        event.candidate_dates
        .all()
        .order_by(
            "date",
            "id",
        )
    )


    # =========================================================
    # Duration options
    # =========================================================

    duration_options = []


    if (
        event.duration_mode
        == Event.DurationMode.VOTE
    ):

        duration_options = list(
            event.duration_options
            .all()
            .order_by(
                "minutes",
                "id",
            )
        )


    # =========================================================
    # Selected duration options
    # =========================================================

    if request.method == "POST":

        selected_duration_option_ids = []


        for option_id in (
            request.POST.getlist(
                "duration_option"
            )
        ):

            try:

                selected_duration_option_ids.append(
                    int(
                        option_id
                    )
                )

            except (
                TypeError,
                ValueError,
            ):

                pass


    else:

        selected_duration_option_ids = list(
            EventDurationVote.objects
            .filter(
                duration_option__event=event,
                user=request.user,
            )
            .values_list(
                "duration_option_id",
                flat=True,
            )
        )


    # =========================================================
    # Add candidate date
    # =========================================================

    if (
        request.method == "POST"
        and
        action == "add_candidate_date"
    ):

        new_candidate_date_value = (
            request.POST.get(
                "new_candidate_date",
                "",
            )
            .strip()
        )


        new_candidate_start_time_value = (
            request.POST.get(
                "new_candidate_start_time",
                "",
            )
            .strip()
        )


        if not can_add_date:

            errors.append(
                "このイベントでは候補日を追加できません。"
            )


        new_date = parse_date(
            new_candidate_date_value
        )


        if new_date is None:

            errors.append(
                "候補日を正しく入力してください。"
            )


        elif (
            event.candidate_dates
            .filter(
                date=new_date,
            )
            .exists()
        ):

            errors.append(
                "その日はすでに候補にあります。"
            )


        new_start_time = None


        if (
            event.scheduling_mode
            == Event.SchedulingMode.START_TIMES
        ):

            normalized_start_time = (
                normalize_time_input(
                    new_candidate_start_time_value
                )
            )


            new_start_time = parse_time(
                normalized_start_time
            )


            if new_start_time is None:

                errors.append(
                    "開始時刻を正しく入力してください。"
                )


        if not errors:

            with transaction.atomic():

                event_date = (
                    EventDate.objects.create(
                        event=event,
                        date=new_date,
                        created_by=request.user,
                    )
                )


                if (
                    event.scheduling_mode
                    == Event.SchedulingMode.START_TIMES
                ):

                    EventStartTimeOption.objects.create(
                        event_date=event_date,
                        start_time=new_start_time,
                        order=0,
                    )


            new_candidate_date_value = ""

            new_candidate_start_time_value = ""


            candidate_dates = list(
                event.candidate_dates
                .all()
                .order_by(
                    "date",
                    "id",
                )
            )


    # =========================================================
    # Add duration
    # =========================================================

    if (
        request.method == "POST"
        and
        action == "add_duration_option"
    ):

        new_duration_minutes_value = (
            request.POST.get(
                "new_duration_minutes",
                "",
            )
            .strip()
        )


        if not can_add_duration:

            errors.append(
                "このイベントでは長さ候補を追加できません。"
            )


        try:

            new_duration_minutes = int(
                new_duration_minutes_value
            )

        except (
            TypeError,
            ValueError,
        ):

            new_duration_minutes = None

            errors.append(
                "長さは数字で入力してください。"
            )


        if new_duration_minutes is not None:

            if (
                new_duration_minutes
                < 15
            ):

                errors.append(
                    "長さは15分以上にしてください。"
                )


            elif (
                new_duration_minutes
                % 15
                != 0
            ):

                errors.append(
                    "長さは15分単位で入力してください。"
                )


        if not errors:

            duration_option = (
                event.duration_options
                .filter(
                    minutes=new_duration_minutes,
                )
                .first()
            )


            if duration_option is None:

                last_order = (
                    event.duration_options
                    .order_by(
                        "-order",
                        "-id",
                    )
                    .values_list(
                        "order",
                        flat=True,
                    )
                    .first()
                )


                next_order = (
                    0
                    if last_order is None
                    else last_order + 1
                )


                duration_option = (
                    EventDurationOption.objects
                    .create(
                        event=event,
                        minutes=new_duration_minutes,
                        order=next_order,
                    )
                )


            EventDurationVote.objects.get_or_create(
                duration_option=duration_option,
                user=request.user,
            )


            if (
                duration_option.id
                not in selected_duration_option_ids
            ):

                selected_duration_option_ids.append(
                    duration_option.id
                )


            new_duration_minutes_value = ""


            duration_options = list(
                event.duration_options
                .all()
                .order_by(
                    "order",
                    "id",
                )
            )


    # =========================================================
    # Save duration votes
    # =========================================================

    def save_duration_votes():

        if (
            event.duration_mode
            != Event.DurationMode.VOTE
        ):

            return


        valid_option_ids = set(
            event.duration_options
            .values_list(
                "id",
                flat=True,
            )
        )


        selected_ids = (
            set(
                selected_duration_option_ids
            )
            &
            valid_option_ids
        )


        EventDurationVote.objects.filter(
            duration_option__event=event,
            user=request.user,
        ).delete()


        EventDurationVote.objects.bulk_create(
            [
                EventDurationVote(
                    duration_option_id=option_id,
                    user=request.user,
                )
                for option_id
                in selected_ids
            ]
        )


    # =========================================================
    # Save response
    # =========================================================

    if (
        request.method == "POST"
        and
        action == "save_response"
    ):

        # -----------------------------------------------------
        # Date only
        # -----------------------------------------------------

        if (
            event.scheduling_mode
            == Event.SchedulingMode.DATE_ONLY
        ):

            with transaction.atomic():

                for candidate in candidate_dates:

                    status = request.POST.get(
                        f"date_status_{candidate.id}",
                        "",
                    )


                    if (
                        status
                        in AvailabilityStatus.values
                    ):

                        EventDateVote.objects.update_or_create(
                            event_date=candidate,
                            user=request.user,
                            defaults={
                                "status":
                                    status,
                            },
                        )

                    else:

                        EventDateVote.objects.filter(
                            event_date=candidate,
                            user=request.user,
                        ).delete()


                save_duration_votes()


            return redirect(
                "event_scheduler:event_detail",
                event_id=event.id,
            )


        # -----------------------------------------------------
        # Time options
        # -----------------------------------------------------

        elif (
            event.scheduling_mode
            == Event.SchedulingMode.TIME_OPTIONS
        ):

            time_options = list(
                event.time_options.all()
            )


            with transaction.atomic():

                for candidate in candidate_dates:

                    for option in time_options:

                        status = request.POST.get(
                            (
                                f"time_option_status_"
                                f"{candidate.id}_"
                                f"{option.id}"
                            ),
                            "",
                        )


                        if (
                            status
                            in AvailabilityStatus.values
                        ):

                            (
                                EventTimeOptionVote.objects
                                .update_or_create(
                                    event_date=candidate,
                                    time_option=option,
                                    user=request.user,
                                    defaults={
                                        "status":
                                            status,
                                    },
                                )
                            )

                        else:

                            (
                                EventTimeOptionVote.objects
                                .filter(
                                    event_date=candidate,
                                    time_option=option,
                                    user=request.user,
                                )
                                .delete()
                            )


                save_duration_votes()


            return redirect(
                "event_scheduler:event_detail",
                event_id=event.id,
            )


        # -----------------------------------------------------
        # Start times
        # -----------------------------------------------------

        elif (
            event.scheduling_mode
            == Event.SchedulingMode.START_TIMES
        ):

            start_options = (
                EventStartTimeOption.objects
                .filter(
                    event_date__event=event,
                )
            )


            with transaction.atomic():

                for option in start_options:

                    status = request.POST.get(
                        f"start_status_{option.id}",
                        "",
                    )


                    if (
                        status
                        in AvailabilityStatus.values
                    ):

                        EventStartTimeVote.objects.update_or_create(
                            start_time_option=option,
                            user=request.user,
                            defaults={
                                "status":
                                    status,
                            },
                        )

                    else:

                        EventStartTimeVote.objects.filter(
                            start_time_option=option,
                            user=request.user,
                        ).delete()


                save_duration_votes()


            return redirect(
                "event_scheduler:event_detail",
                event_id=event.id,
            )


        # -----------------------------------------------------
        # Free input
        # -----------------------------------------------------

        elif (
            event.scheduling_mode
            == Event.SchedulingMode.FREE_INPUT
        ):

            responses_to_save = []


            for candidate in candidate_dates:

                response_type = request.POST.get(
                    f"response_type_{candidate.id}",
                    "",
                )


                note = request.POST.get(
                    f"note_{candidate.id}",
                    "",
                ).strip()


                if not response_type:

                    responses_to_save.append(
                        {
                            "candidate":
                                candidate,

                            "response_type":
                                None,
                        }
                    )

                    continue


                if (
                    response_type
                    not in EventDateResponse.ResponseType.values
                ):

                    errors.append(
                        (
                            f"{candidate.date} の回答が"
                            "正しくありません。"
                        )
                    )

                    continue


                windows = []


                if (
                    response_type
                    ==
                    EventDateResponse.ResponseType.PARTIAL
                ):

                    starts = request.POST.getlist(
                        f"free_start_{candidate.id}"
                    )


                    ends = request.POST.getlist(
                        f"free_end_{candidate.id}"
                    )


                    for start, end in zip(
                        starts,
                        ends,
                    ):

                        start = normalize_time_input(
                            start
                        )


                        end = normalize_time_input(
                            end
                        )


                        if (
                            not start
                            and
                            not end
                        ):

                            continue


                        parsed_start = parse_time(
                            start
                        )


                        parsed_end = parse_time(
                            end
                        )


                        if (
                            not parsed_start
                            or
                            not parsed_end
                        ):

                            errors.append(
                                (
                                    f"{candidate.date} の時間を"
                                    "正しく入力してください。"
                                )
                            )

                            continue


                        if (
                            parsed_end
                            <=
                            parsed_start
                        ):

                            errors.append(
                                (
                                    f"{candidate.date} の"
                                    "終了時刻は開始時刻より"
                                    "後にしてください。"
                                )
                            )

                            continue


                        windows.append(
                            (
                                parsed_start,
                                parsed_end,
                            )
                        )


                    if not windows:

                        errors.append(
                            (
                                f"{candidate.date} は"
                                "時間を1つ以上入力してください。"
                            )
                        )


                responses_to_save.append(
                    {
                        "candidate":
                            candidate,

                        "response_type":
                            response_type,

                        "note":
                            note,

                        "windows":
                            windows,
                    }
                )


            if not errors:

                with transaction.atomic():

                    for item in responses_to_save:

                        candidate = item[
                            "candidate"
                        ]


                        if not item[
                            "response_type"
                        ]:

                            EventDateResponse.objects.filter(
                                event_date=candidate,
                                user=request.user,
                            ).delete()

                            continue


                        response, created = (
                            EventDateResponse.objects
                            .update_or_create(
                                event_date=candidate,
                                user=request.user,
                                defaults={
                                    "response_type":
                                        item[
                                            "response_type"
                                        ],

                                    "note":
                                        item[
                                            "note"
                                        ],
                                },
                            )
                        )


                        response.windows.all().delete()


                        if (
                            item["response_type"]
                            ==
                            EventDateResponse.ResponseType.PARTIAL
                        ):

                            for (
                                start_time,
                                end_time,
                            ) in item["windows"]:

                                AvailabilityWindow.objects.create(
                                    response=response,
                                    start_time=start_time,
                                    end_time=end_time,
                                )


                    save_duration_votes()


                return redirect(
                    "event_scheduler:event_detail",
                    event_id=event.id,
                )


    # =========================================================
    # Keep current form values on POST
    # =========================================================

    preserve_posted_response = (
        request.method == "POST"
    )


    # =========================================================
    # Build template rows
    # =========================================================

    date_rows = []


    for candidate in candidate_dates:

        row = {
            "candidate":
                candidate,
        }


        # -----------------------------------------------------
        # Date only
        # -----------------------------------------------------

        if (
            event.scheduling_mode
            == Event.SchedulingMode.DATE_ONLY
        ):

            if preserve_posted_response:

                row["status"] = (
                    request.POST.get(
                        f"date_status_{candidate.id}",
                        "",
                    )
                )

            else:

                vote = (
                    EventDateVote.objects
                    .filter(
                        event_date=candidate,
                        user=request.user,
                    )
                    .first()
                )


                row["status"] = (
                    vote.status
                    if vote
                    else ""
                )


        # -----------------------------------------------------
        # Time options
        # -----------------------------------------------------

        elif (
            event.scheduling_mode
            == Event.SchedulingMode.TIME_OPTIONS
        ):

            options = []


            for option in event.time_options.all():

                if preserve_posted_response:

                    status = request.POST.get(
                        (
                            f"time_option_status_"
                            f"{candidate.id}_"
                            f"{option.id}"
                        ),
                        "",
                    )

                else:

                    vote = (
                        EventTimeOptionVote.objects
                        .filter(
                            event_date=candidate,
                            time_option=option,
                            user=request.user,
                        )
                        .first()
                    )


                    status = (
                        vote.status
                        if vote
                        else ""
                    )


                options.append(
                    {
                        "option":
                            option,

                        "status":
                            status,
                    }
                )


            row["options"] = options


        # -----------------------------------------------------
        # Start times
        # -----------------------------------------------------

        elif (
            event.scheduling_mode
            == Event.SchedulingMode.START_TIMES
        ):

            options = []


            for option in (
                candidate
                .start_time_options
                .all()
            ):

                if preserve_posted_response:

                    status = request.POST.get(
                        f"start_status_{option.id}",
                        "",
                    )

                else:

                    vote = (
                        EventStartTimeVote.objects
                        .filter(
                            start_time_option=option,
                            user=request.user,
                        )
                        .first()
                    )


                    status = (
                        vote.status
                        if vote
                        else ""
                    )


                options.append(
                    {
                        "option":
                            option,

                        "status":
                            status,
                    }
                )


            row["options"] = options


        # -----------------------------------------------------
        # Free input
        # -----------------------------------------------------

        elif (
            event.scheduling_mode
            == Event.SchedulingMode.FREE_INPUT
        ):

            if preserve_posted_response:

                row["response_type"] = (
                    request.POST.get(
                        f"response_type_{candidate.id}",
                        "",
                    )
                )


                row["note"] = (
                    request.POST.get(
                        f"note_{candidate.id}",
                        "",
                    )
                )


                starts = request.POST.getlist(
                    f"free_start_{candidate.id}"
                )


                ends = request.POST.getlist(
                    f"free_end_{candidate.id}"
                )


                posted_windows = []


                for start, end in zip(
                    starts,
                    ends,
                ):

                    start = normalize_time_input(
                        start
                    )


                    end = normalize_time_input(
                        end
                    )


                    if (
                        not start
                        and
                        not end
                    ):

                        continue


                    posted_windows.append(
                        {
                            "start":
                                start,

                            "end":
                                end,
                        }
                    )


                row["posted_windows"] = (
                    posted_windows
                )

                row["windows"] = []


            else:

                response = (
                    EventDateResponse.objects
                    .filter(
                        event_date=candidate,
                        user=request.user,
                    )
                    .prefetch_related(
                        "windows",
                    )
                    .first()
                )


                row["posted_windows"] = []


                if response:

                    row["response_type"] = (
                        response.response_type
                    )

                    row["note"] = (
                        response.note
                    )

                    row["windows"] = list(
                        response.windows.all()
                    )


                else:

                    row["response_type"] = ""

                    row["note"] = ""

                    row["windows"] = []


        date_rows.append(
            row
        )


    return render(
        request,
        "event_scheduler/event_respond.html",
        {
            "event":
                event,

            "date_rows":
                date_rows,

            "errors":
                errors,

            "can_add_date":
                can_add_date,

            "can_add_duration":
                can_add_duration,

            "duration_options":
                duration_options,

            "selected_duration_option_ids":
                selected_duration_option_ids,

            "new_candidate_date_value":
                new_candidate_date_value,

            "new_candidate_start_time_value":
                new_candidate_start_time_value,

            "new_duration_minutes_value":
                new_duration_minutes_value,
        },
    )

# =========================================================
# Event admins
# =========================================================

@login_required
def event_admins(
    request,
    event_id,
):

    event = get_object_or_404(
        Event,
        id=event_id,
    )


    if not event.can_manage(
        request.user
    ):

        return redirect(
            "event_scheduler:event_detail",
            event_id=event.id,
        )


    admins = (
        event.admins
        .select_related(
            "user"
        )
        .all()
    )


    pending_invitations = (
        event.admin_invitations
        .filter(
            status=EventAdminInvitation.Status.PENDING,
        )
        .select_related(
            "invited_user",
            "invited_by",
        )
    )


    form = EventAdminInviteForm()


    return render(
        request,
        "event_scheduler/event_admins.html",
        {
            "event":
                event,

            "admins":
                admins,

            "admin_count":
                admins.count(),

            "pending_invitations":
                pending_invitations,

            "form":
                form,
        },
    )


@login_required
def event_admin_invite(
    request,
    event_id,
):

    event = get_object_or_404(
        Event,
        id=event_id,
    )


    if not event.can_manage(
        request.user
    ):

        return redirect(
            "event_scheduler:event_detail",
            event_id=event.id,
        )


    if request.method != "POST":

        return redirect(
            "event_scheduler:event_admins",
            event_id=event.id,
        )


    form = EventAdminInviteForm(
        request.POST
    )


    if form.is_valid():

        username = (
            form.cleaned_data[
                "username"
            ]
            .strip()
        )


        UserModel = get_user_model()

        username_field = (
            UserModel.USERNAME_FIELD
        )


        invited_user = (
            UserModel.objects
            .filter(
                **{
                    username_field:
                        username,
                }
            )
            .first()
        )


        if invited_user is None:

            messages.error(
                request,
                "そのログインIDのユーザーは見つかりません。",
            )


        elif event.admins.filter(
            user=invited_user
        ).exists():

            messages.error(
                request,
                "このユーザーはすでに管理者です。",
            )


        else:

            invitation, created = (
                EventAdminInvitation.objects
                .update_or_create(
                    event=event,
                    invited_user=invited_user,
                    defaults={
                        "invited_by":
                            request.user,

                        "status":
                            EventAdminInvitation.Status.PENDING,
                    },
                )
            )


            messages.success(
                request,
                "共同管理者として招待しました。",
            )


    return redirect(
        "event_scheduler:event_admins",
        event_id=event.id,
    )


@login_required
def event_admin_invitation_accept(
    request,
    invitation_id,
):

    invitation = get_object_or_404(
        EventAdminInvitation,
        id=invitation_id,
        invited_user=request.user,
        status=EventAdminInvitation.Status.PENDING,
    )


    if request.method == "POST":

        with transaction.atomic():

            EventAdmin.objects.get_or_create(
                event=invitation.event,
                user=request.user,
            )


            # 管理者になったら参加者にもする
            participant, created = (
                EventParticipant.objects
                .get_or_create(
                    event=invitation.event,
                    user=request.user,
                )
            )

            participant.status = (
                EventParticipant.Status.JOINED
            )

            participant.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )


            invitation.status = (
                EventAdminInvitation.Status.ACCEPTED
            )

            invitation.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )


    return redirect(
        "event_scheduler:event_detail",
        event_id=invitation.event.id,
    )


@login_required
def event_admin_invitation_decline(
    request,
    invitation_id,
):

    invitation = get_object_or_404(
        EventAdminInvitation,
        id=invitation_id,
        invited_user=request.user,
        status=EventAdminInvitation.Status.PENDING,
    )


    if request.method == "POST":

        invitation.status = (
            EventAdminInvitation.Status.DECLINED
        )

        invitation.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )


    return redirect(
        "event_scheduler:event_detail",
        event_id=invitation.event.id,
    )


@login_required
def event_admin_invitation_cancel(
    request,
    event_id,
    invitation_id,
):

    event = get_object_or_404(
        Event,
        id=event_id,
    )


    if not event.can_manage(
        request.user
    ):

        return redirect(
            "event_scheduler:event_detail",
            event_id=event.id,
        )


    invitation = get_object_or_404(
        EventAdminInvitation,
        id=invitation_id,
        event=event,
        status=EventAdminInvitation.Status.PENDING,
    )


    if request.method == "POST":

        invitation.delete()


    return redirect(
        "event_scheduler:event_admins",
        event_id=event.id,
    )



@login_required
def event_admin_remove(
    request,
    event_id,
    admin_id,
):

    event = get_object_or_404(
        Event,
        id=event_id,
    )


    if not event.can_manage(
        request.user
    ):

        return redirect(
            "event_scheduler:event_detail",
            event_id=event.id,
        )


    admin = get_object_or_404(
        EventAdmin,
        id=admin_id,
        event=event,
    )


    if request.method == "POST":

        admin_count = (
            event.admins.count()
        )


        if admin_count <= 1:

            messages.error(
                request,
                "最後の管理者は削除できません。",
            )


        elif admin.user == request.user:

            messages.error(
                request,
                "自分自身は「管理者から退出」から操作してください。",
            )


        else:

            admin.delete()

            messages.success(
                request,
                "共同管理者を削除しました。",
            )


    return redirect(
        "event_scheduler:event_admins",
        event_id=event.id,
    )


@login_required
def event_admin_leave(
    request,
    event_id,
):

    event = get_object_or_404(
        Event,
        id=event_id,
    )


    admin = (
        event.admins
        .filter(
            user=request.user
        )
        .first()
    )


    if admin is None:

        return redirect(
            "event_scheduler:event_detail",
            event_id=event.id,
        )


    if request.method == "POST":

        if event.admins.count() <= 1:

            messages.error(
                request,
                (
                    "あなたが最後の管理者なので、"
                    "管理者から退出できません。"
                ),
            )

            return redirect(
                "event_scheduler:event_admins",
                event_id=event.id,
            )


        admin.delete()


        messages.success(
            request,
            "イベントの管理者から退出しました。",
        )


    return redirect(
        "event_scheduler:event_detail",
        event_id=event.id,
    )




@login_required
def event_archive(
    request,
    event_id,
):

    event = get_object_or_404(
        Event,
        id=event_id,
    )


    if not event.can_manage(
        request.user
    ):

        return redirect(
            "event_scheduler:event_detail",
            event_id=event.id,
        )


    if request.method == "POST":

        event.is_archived = True
        event.archived_at = timezone.now()

        event.save(
            update_fields=[
                "is_archived",
                "archived_at",
            ]
        )


    return redirect(
        "event_scheduler:event_list"
    )

@login_required
def event_restore(
    request,
    event_id,
):

    event = get_object_or_404(
        Event,
        id=event_id,
    )


    if not event.can_manage(
        request.user
    ):

        return redirect(
            "event_scheduler:event_detail",
            event_id=event.id,
        )


    if request.method == "POST":

        event.is_archived = False
        event.archived_at = None

        event.save(
            update_fields=[
                "is_archived",
                "archived_at",
            ]
        )


    return redirect(
        "event_scheduler:event_detail",
        event_id=event.id,
    )

@login_required
def event_delete(
    request,
    event_id,
):

    event = get_object_or_404(
        Event,
        id=event_id,
    )


    if request.user != event.creator:

        return redirect(
            "event_scheduler:event_detail",
            event_id=event.id,
        )


    if request.method == "POST":

        event.delete()

        return redirect(
            "event_scheduler:event_list"
        )


    return render(
        request,
        "event_scheduler/event_confirm_delete.html",
        {
            "event": event,
        },
    )