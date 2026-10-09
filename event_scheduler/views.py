from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Max, Q
from travel.models import UserProfile
from django.views.decorators.http import require_http_methods

from django.http import (
    HttpResponseBadRequest,
    HttpResponseForbidden,
)


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
    EventSettingsForm,
    EventParticipantInviteForm,
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
    EventGuestParticipant,
    EventParticipant,
    EventStartTimeOption,
    EventStartTimeVote,
    EventTimeOption,
    EventTimeOptionVote,
)



# =========================================================
# Event list
# =========================================================

def event_list(request):

    # =====================================================
    # Defaults for anonymous users
    # =====================================================

    events = Event.objects.none()

    pending_participant_invitations = (
        EventParticipant.objects.none()
    )

    pending_admin_invitations = (
        EventAdminInvitation.objects.none()
    )

    # =====================================================
    # Public events: available to everyone
    # =====================================================

    public_events = (
        Event.objects
        .filter(
            is_public=True,
            is_archived=False,
        )
        .distinct()
    )

    # =====================================================
    # Logged-in users
    # =====================================================

    if request.user.is_authenticated:

        # My joined events

        events = (
            Event.objects
            .filter(
                participants__user=request.user,
                participants__status=EventParticipant.Status.JOINED,
                is_archived=False,
            )
            .distinct()
        )

        # Participant invitations

        pending_participant_invitations = (
            EventParticipant.objects
            .filter(
                user=request.user,
                status=EventParticipant.Status.INVITED,
                event__is_archived=False,
            )
            .select_related("event")
            .order_by("-updated_at")
        )

        # Avoid duplicate public events

        hidden_public_event_ids = (
            EventParticipant.objects
            .filter(
                user=request.user,
                status__in=[
                    EventParticipant.Status.JOINED,
                    EventParticipant.Status.INVITED,
                ],
            )
            .values_list(
                "event_id",
                flat=True,
            )
        )

        public_events = public_events.exclude(
            id__in=hidden_public_event_ids
        )

        # Admin invitations

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
            .order_by("-created_at")
        )

    # =====================================================
    # Render
    # =====================================================

    return render(
        request,
        "event_scheduler/event_list.html",
        {
            "events": events,
            "public_events": public_events,
            "pending_admin_invitations": pending_admin_invitations,
            "pending_participant_invitations": pending_participant_invitations,
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
# Shared event results
# Logged-in users + guests
# =========================================================

def build_event_results(event):

    candidate_dates = list(
        event.candidate_dates.all().order_by("date", "id")
    )

    joined_count = EventParticipant.objects.filter(
        event=event,
        status=EventParticipant.Status.JOINED,
    ).count()

    guest_count = EventGuestParticipant.objects.filter(
        event=event,
    ).filter(
        Q(date_votes__isnull=False)
        | Q(time_option_votes__isnull=False)
        | Q(start_time_votes__isnull=False)
        | Q(date_responses__isnull=False)
    ).distinct().count()

    participant_count = joined_count + guest_count

    user_ids = EventParticipant.objects.filter(
        event=event,
        status=EventParticipant.Status.JOINED,
    ).values_list("user_id", flat=True)

    nickname_map = dict(
        UserProfile.objects.filter(
            user_id__in=user_ids,
        ).values_list("user_id", "nickname")
    )

    def display_name(item):

        if item.guest_id:
            return item.guest.display_name

        if item.user_id:
            nickname = (
                nickname_map.get(item.user_id, "") or ""
            ).strip()

            return nickname or item.user.get_username()

        return "不明"

    def vote_breakdown(queryset):

        groups = {
            "yes": [],
            "maybe": [],
            "no": [],
        }

        for vote in queryset.select_related("user", "guest"):

            if vote.status in groups:
                groups[vote.status].append(
                    display_name(vote)
                )

        for names in groups.values():
            names.sort(key=str.casefold)

        return {
            "yes_count": len(groups["yes"]),
            "maybe_count": len(groups["maybe"]),
            "no_count": len(groups["no"]),
            "yes_users": groups["yes"],
            "maybe_users": groups["maybe"],
            "no_users": groups["no"],
        }

    result_rows = []

    # -----------------------------------------------------
    # Date only
    # -----------------------------------------------------

    if event.scheduling_mode == Event.SchedulingMode.DATE_ONLY:

        for candidate in candidate_dates:

            breakdown = vote_breakdown(
                EventDateVote.objects.filter(
                    event_date=candidate,
                )
            )

            result_rows.append({
                "date": candidate.date,
                "label": "",
                "start_time": None,
                "end_time": None,
                **breakdown,
            })

    # -----------------------------------------------------
    # Time options
    # -----------------------------------------------------

    elif event.scheduling_mode == Event.SchedulingMode.TIME_OPTIONS:

        options = event.time_options.all().order_by(
            "order", "id"
        )

        for candidate in candidate_dates:
            for option in options:

                breakdown = vote_breakdown(
                    EventTimeOptionVote.objects.filter(
                        event_date=candidate,
                        time_option=option,
                    )
                )

                result_rows.append({
                    "date": candidate.date,
                    "label": option.label,
                    "start_time": option.start_time,
                    "end_time": option.end_time,
                    **breakdown,
                })

    # -----------------------------------------------------
    # Start times
    # -----------------------------------------------------

    elif event.scheduling_mode == Event.SchedulingMode.START_TIMES:

        options = (
            EventStartTimeOption.objects.filter(
                event_date__event=event,
            )
            .select_related("event_date")
            .order_by(
                "event_date__date",
                "start_time",
                "id",
            )
        )

        for option in options:

            breakdown = vote_breakdown(
                EventStartTimeVote.objects.filter(
                    start_time_option=option,
                )
            )

            result_rows.append({
                "date": option.event_date.date,
                "label": "",
                "start_time": option.start_time,
                "end_time": None,
                **breakdown,
            })

    # -----------------------------------------------------
    # Free input
    # -----------------------------------------------------

    elif event.scheduling_mode == Event.SchedulingMode.FREE_INPUT:

        for candidate in candidate_dates:

            groups = {
                "yes": [],
                "maybe": [],
                "no": [],
            }

            responses = (
                EventDateResponse.objects.filter(
                    event_date=candidate,
                )
                .select_related("user", "guest")
            )

            for response in responses:

                if response.response_type == (
                    EventDateResponse.ResponseType.ALL_DAY
                ):
                    key = "yes"

                elif response.response_type == (
                    EventDateResponse.ResponseType.PARTIAL
                ):
                    key = "maybe"

                elif response.response_type == (
                    EventDateResponse.ResponseType.UNAVAILABLE
                ):
                    key = "no"

                else:
                    continue

                groups[key].append(
                    display_name(response)
                )

            for names in groups.values():
                names.sort(key=str.casefold)

            result_rows.append({
                "date": candidate.date,
                "label": "",
                "start_time": None,
                "end_time": None,
                "yes_count": len(groups["yes"]),
                "maybe_count": len(groups["maybe"]),
                "no_count": len(groups["no"]),
                "yes_users": groups["yes"],
                "maybe_users": groups["maybe"],
                "no_users": groups["no"],
            })

    # =====================================================
    # Recommended Top 3
    # =====================================================

    answered_rows = [
        row for row in result_rows
        if (
            row["yes_count"]
            + row["maybe_count"]
            + row["no_count"]
        ) > 0
    ]

    for row in answered_rows:
        row["recommendation_score"] = (
            row["yes_count"] * 2
            + row["maybe_count"]
            - row["no_count"] * 2
        )

    top_result_rows = sorted(
        answered_rows,
        key=lambda row: (
            row["recommendation_score"],
            row["yes_count"],
            -row["no_count"],
            row["maybe_count"],
        ),
        reverse=True,
    )[:3]

    # =====================================================
    # Duration results
    # =====================================================

    duration_result_rows = []

    if event.duration_mode == Event.DurationMode.VOTE:

        for option in event.duration_options.all().order_by(
            "minutes", "id"
        ):

            votes = list(
                EventDurationVote.objects.filter(
                    duration_option=option,
                ).select_related("user", "guest")
            )

            voters = sorted(
                [display_name(vote) for vote in votes],
                key=str.casefold,
            )

            vote_count = len(voters)

            vote_percent = (
                round(vote_count / participant_count * 100)
                if participant_count
                else 0
            )

            duration_result_rows.append({
                "option": option,
                "vote_count": vote_count,
                "vote_percent": vote_percent,
                "voters": voters,
            })

    return {
        "joined_participant_count": participant_count,
        "result_rows": result_rows,
        "top_result_rows": top_result_rows,
        "duration_result_rows": duration_result_rows,
    }


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
    # Shared results
    # =========================================================

    result_rows = []
    top_result_rows = []
    duration_result_rows = []

    joined_participant_count = (
        EventParticipant.objects.filter(
            event=event,
            status=EventParticipant.Status.JOINED,
        ).count()
    )

    if has_answered:

        results = build_event_results(event)

        result_rows = results["result_rows"]
        top_result_rows = results["top_result_rows"]
        duration_result_rows = results["duration_result_rows"]

        joined_participant_count = results[
            "joined_participant_count"
        ]

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

            "joined_participant_count":
                joined_participant_count,

            "result_rows":
                result_rows,
            
            "top_result_rows":
                top_result_rows,

            "duration_result_rows":
                duration_result_rows,
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
# Leave public event
# =========================================================

@login_required
def leave_event(
    request,
    event_id,
):

    event = get_object_or_404(
        Event,
        id=event_id,
    )


    participant = get_object_or_404(
        EventParticipant,
        event=event,
        user=request.user,
        status=EventParticipant.Status.JOINED,
    )


    # =========================================================
    # Admin cannot leave here
    # =========================================================

    if event.can_manage(
        request.user
    ):

        return redirect(
            "event_scheduler:event_detail",
            event_id=event.id,
        )


    # =========================================================
    # Leave
    # =========================================================

    if request.method == "POST":

        with transaction.atomic():

            # -------------------------------------------------
            # Date-only votes
            # -------------------------------------------------

            EventDateVote.objects.filter(
                event_date__event=event,
                user=request.user,
            ).delete()


            # -------------------------------------------------
            # Time-option votes
            # -------------------------------------------------

            EventTimeOptionVote.objects.filter(
                event_date__event=event,
                user=request.user,
            ).delete()


            # -------------------------------------------------
            # Start-time votes
            # -------------------------------------------------

            EventStartTimeVote.objects.filter(
                start_time_option__event_date__event=event,
                user=request.user,
            ).delete()


            # -------------------------------------------------
            # Free-input responses
            # -------------------------------------------------

            EventDateResponse.objects.filter(
                event_date__event=event,
                user=request.user,
            ).delete()


            # -------------------------------------------------
            # Duration votes
            # -------------------------------------------------

            EventDurationVote.objects.filter(
                duration_option__event=event,
                user=request.user,
            ).delete()


            # -------------------------------------------------
            # Participant
            # -------------------------------------------------

            participant.delete()


        return redirect(
            "event_scheduler:event_list"
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


    # =========================================================
    # Permissions
    # =========================================================

    can_manage = event.can_manage(
        request.user
    )


    # FREE_INPUT では候補日追加を常に許可
    can_add_date = (
        can_manage
        or event.allow_participant_date_addition
    )


    can_add_time_option = (
        event.scheduling_mode
        == Event.SchedulingMode.TIME_OPTIONS
        and
        (
            can_manage
            or
            event.allow_participant_time_option_addition
        )
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


    # =========================================================
    # General values
    # =========================================================

    errors = []


    new_candidate_date_value = ""

    new_candidate_start_time_value = ""


    new_time_option_label_value = ""

    new_time_option_start_value = ""

    new_time_option_end_value = ""


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
            "add_time_option"
            in request.POST
        ):

            action = "add_time_option"


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
    # Add candidate
    #
    # DATE_ONLY:
    #   date
    #
    # TIME_OPTIONS:
    #   date
    #
    # START_TIMES:
    #   date + start time
    #
    # FREE_INPUT:
    #   date
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


        # -----------------------------------------------------
        # Permission
        # -----------------------------------------------------

        if not can_add_date:

            errors.append(
                "このイベントでは候補を追加できません。"
            )


        # -----------------------------------------------------
        # Date
        # -----------------------------------------------------

        new_date = parse_date(
            new_candidate_date_value
        )


        if new_date is None:

            errors.append(
                "候補日を正しく入力してください。"
            )


        # -----------------------------------------------------
        # START TIMES
        #
        # 日付 + 開始時刻で1つの候補
        # -----------------------------------------------------

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


            # 同じ日付自体はOK。
            # 同じ「日付 + 開始時刻」は重複不可。

            if (
                new_date is not None
                and
                new_start_time is not None
            ):

                existing_date = (
                    event.candidate_dates
                    .filter(
                        date=new_date,
                    )
                    .first()
                )


                if (
                    existing_date
                    and
                    existing_date
                    .start_time_options
                    .filter(
                        start_time=new_start_time,
                    )
                    .exists()
                ):

                    errors.append(
                        "その候補日時はすでにあります。"
                    )


        # -----------------------------------------------------
        # Other modes
        #
        # DATE_ONLY / TIME_OPTIONS / FREE_INPUT
        # では同じ候補日の重複は不可
        # -----------------------------------------------------

        elif (
            new_date is not None
            and
            event.candidate_dates
            .filter(
                date=new_date,
            )
            .exists()
        ):

            errors.append(
                "その日はすでに候補にあります。"
            )


        # -----------------------------------------------------
        # Save
        # -----------------------------------------------------

        if not errors:

            with transaction.atomic():

                # ---------------------------------------------
                # START TIMES
                # ---------------------------------------------

                if (
                    event.scheduling_mode
                    == Event.SchedulingMode.START_TIMES
                ):

                    event_date, created = (
                        EventDate.objects
                        .get_or_create(
                            event=event,
                            date=new_date,
                            defaults={
                                "created_by":
                                    request.user,
                            },
                        )
                    )


                    last_order = (
                        event_date
                        .start_time_options
                        .aggregate(
                            max_order=Max(
                                "order"
                            )
                        )
                        .get(
                            "max_order"
                        )
                    )


                    next_order = (
                        0
                        if last_order is None
                        else last_order + 1
                    )


                    EventStartTimeOption.objects.create(
                        event_date=event_date,
                        start_time=new_start_time,
                        order=next_order,
                    )


                # ---------------------------------------------
                # Other modes
                # ---------------------------------------------

                else:

                    EventDate.objects.create(
                        event=event,
                        date=new_date,
                        created_by=request.user,
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
    # Add time option
    #
    # TIME_OPTIONS only
    #
    # 例:
    #   夕方
    #   17:00 - 20:00
    #
    # 時刻なしで「夕方」だけでもOK
    # =========================================================

    if (
        request.method == "POST"
        and
        action == "add_time_option"
    ):

        new_time_option_label_value = (
            request.POST.get(
                "new_time_option_label",
                "",
            )
            .strip()
        )


        new_time_option_start_value = (
            request.POST.get(
                "new_time_option_start",
                "",
            )
            .strip()
        )


        new_time_option_end_value = (
            request.POST.get(
                "new_time_option_end",
                "",
            )
            .strip()
        )


        # -----------------------------------------------------
        # Permission
        # -----------------------------------------------------

        if not can_add_time_option:

            errors.append(
                "このイベントでは時間帯を追加できません。"
            )


        # -----------------------------------------------------
        # Label
        # -----------------------------------------------------

        if not new_time_option_label_value:

            errors.append(
                "時間帯の名前を入力してください。"
            )


        # -----------------------------------------------------
        # Times
        # -----------------------------------------------------

        normalized_start = (
            normalize_time_input(
                new_time_option_start_value
            )
        )


        normalized_end = (
            normalize_time_input(
                new_time_option_end_value
            )
        )


        parsed_start = (
            parse_time(
                normalized_start
            )
            if normalized_start
            else None
        )


        parsed_end = (
            parse_time(
                normalized_end
            )
            if normalized_end
            else None
        )


        if (
            normalized_start
            and
            parsed_start is None
        ):

            errors.append(
                "開始時刻を正しく入力してください。"
            )


        if (
            normalized_end
            and
            parsed_end is None
        ):

            errors.append(
                "終了時刻を正しく入力してください。"
            )


        if (
            bool(parsed_start)
            !=
            bool(parsed_end)
        ):

            errors.append(
                (
                    "開始時刻と終了時刻は"
                    "両方入力するか、"
                    "両方空欄にしてください。"
                )
            )


        if (
            parsed_start
            and
            parsed_end
            and
            parsed_end <= parsed_start
        ):

            errors.append(
                "終了時刻は開始時刻より後にしてください。"
            )


        # -----------------------------------------------------
        # Duplicate
        # -----------------------------------------------------

        if (
            not errors
            and
            event.time_options
            .filter(
                label=new_time_option_label_value,
                start_time=parsed_start,
                end_time=parsed_end,
            )
            .exists()
        ):

            errors.append(
                "その時間帯はすでにあります。"
            )


        # -----------------------------------------------------
        # Save
        # -----------------------------------------------------

        if not errors:

            last_order = (
                event.time_options
                .aggregate(
                    max_order=Max(
                        "order"
                    )
                )
                .get(
                    "max_order"
                )
            )


            next_order = (
                0
                if last_order is None
                else last_order + 1
            )


            EventTimeOption.objects.create(
                event=event,
                label=new_time_option_label_value,
                start_time=parsed_start,
                end_time=parsed_end,
                order=next_order,
            )


            new_time_option_label_value = ""

            new_time_option_start_value = ""

            new_time_option_end_value = ""


    # =========================================================
    # Add duration option
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


        # -----------------------------------------------------
        # Permission
        # -----------------------------------------------------

        if not can_add_duration:

            errors.append(
                "このイベントでは長さ候補を追加できません。"
            )


        # -----------------------------------------------------
        # Validate
        # -----------------------------------------------------

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


        if (
            new_duration_minutes
            is not None
        ):

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


        # -----------------------------------------------------
        # Save
        # -----------------------------------------------------

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
                    .aggregate(
                        max_order=Max(
                            "order"
                        )
                    )
                    .get(
                        "max_order"
                    )
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


            # 追加した本人については
            # その候補を選択済みにする

            EventDurationVote.objects.get_or_create(
                duration_option=duration_option,
                user=request.user,
            )


            if (
                duration_option.id
                not in
                selected_duration_option_ids
            ):

                selected_duration_option_ids.append(
                    duration_option.id
                )


            new_duration_minutes_value = ""


            # 短い順で再取得

            duration_options = list(
                event.duration_options
                .all()
                .order_by(
                    "minutes",
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
        # Mode 1:
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
        # Mode 2:
        # Time options
        # -----------------------------------------------------

        elif (
            event.scheduling_mode
            == Event.SchedulingMode.TIME_OPTIONS
        ):

            time_options = list(
                event.time_options
                .all()
                .order_by(
                    "order",
                    "id",
                )
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
        # Mode 3:
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
                .order_by(
                    "event_date__date",
                    "start_time",
                    "id",
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
        # Mode 4:
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


                # ---------------------------------------------
                # No response
                # ---------------------------------------------

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


                # ---------------------------------------------
                # Invalid response
                # ---------------------------------------------

                if (
                    response_type
                    not in
                    EventDateResponse.ResponseType.values
                ):

                    errors.append(
                        (
                            f"{candidate.date} の回答が"
                            "正しくありません。"
                        )
                    )

                    continue


                windows = []


                # ---------------------------------------------
                # Partial
                # ---------------------------------------------

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
    # Preserve current input on POST
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
        # Mode 1:
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
        # Mode 2:
        # Time options
        # -----------------------------------------------------

        elif (
            event.scheduling_mode
            == Event.SchedulingMode.TIME_OPTIONS
        ):

            options = []


            for option in (
                event.time_options
                .all()
                .order_by(
                    "order",
                    "id",
                )
            ):

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


            row["options"] = (
                options
            )


        # -----------------------------------------------------
        # Mode 3:
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
                .order_by(
                    "start_time",
                    "id",
                )
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


            row["options"] = (
                options
            )


        # -----------------------------------------------------
        # Mode 4:
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


    # =========================================================
    # Render
    # =========================================================

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

            "can_add_time_option":
                can_add_time_option,

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

            "new_time_option_label_value":
                new_time_option_label_value,

            "new_time_option_start_value":
                new_time_option_start_value,

            "new_time_option_end_value":
                new_time_option_end_value,

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


# =========================================================
# Event participants
# =========================================================

@login_required
def event_participants(
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


    joined_participants = (
        event.participants
        .filter(
            status=EventParticipant.Status.JOINED,
        )
        .select_related(
            "user",
        )
        .order_by(
            "user__username",
        )
    )


    pending_invitations = (
        event.participants
        .filter(
            status=EventParticipant.Status.INVITED,
        )
        .select_related(
            "user",
        )
        .order_by(
            "-updated_at",
        )
    )


    form = EventParticipantInviteForm()


    return render(
        request,
        "event_scheduler/event_participants.html",
        {
            "event":
                event,

            "joined_participants":
                joined_participants,

            "participant_count":
                joined_participants.count(),

            "pending_invitations":
                pending_invitations,

            "form":
                form,
        },
    )


# =========================================================
# Invite participant
# =========================================================

@login_required
def event_participant_invite(
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
            "event_scheduler:event_participants",
            event_id=event.id,
        )


    form = EventParticipantInviteForm(
        request.POST,
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


        # -----------------------------------------------------
        # User not found
        # -----------------------------------------------------

        if invited_user is None:

            messages.error(
                request,
                "そのログインIDのユーザーは見つかりません。",
            )


        # -----------------------------------------------------
        # Already joined
        # -----------------------------------------------------

        elif (
            EventParticipant.objects
            .filter(
                event=event,
                user=invited_user,
                status=EventParticipant.Status.JOINED,
            )
            .exists()
        ):

            messages.error(
                request,
                "このユーザーはすでに参加しています。",
            )


        # -----------------------------------------------------
        # Already invited
        # -----------------------------------------------------

        elif (
            EventParticipant.objects
            .filter(
                event=event,
                user=invited_user,
                status=EventParticipant.Status.INVITED,
            )
            .exists()
        ):

            messages.error(
                request,
                "このユーザーはすでに招待されています。",
            )


        # -----------------------------------------------------
        # Invite
        # -----------------------------------------------------

        else:

            participant, created = (
                EventParticipant.objects
                .get_or_create(
                    event=event,
                    user=invited_user,
                )
            )


            participant.status = (
                EventParticipant.Status.INVITED
            )

            participant.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )


            messages.success(
                request,
                "参加者として招待しました。",
            )


    return redirect(
        "event_scheduler:event_participants",
        event_id=event.id,
    )


# =========================================================
# Accept participant invitation
# =========================================================

@login_required
def event_participant_invitation_accept(
    request,
    participant_id,
):

    participant = get_object_or_404(
        EventParticipant,
        id=participant_id,
        user=request.user,
        status=EventParticipant.Status.INVITED,
    )


    if request.method == "POST":

        participant.status = (
            EventParticipant.Status.JOINED
        )

        participant.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )


        messages.success(
            request,
            "イベントに参加しました。",
        )


    return redirect(
        "event_scheduler:event_detail",
        event_id=participant.event.id,
    )


# =========================================================
# Decline participant invitation
# =========================================================

@login_required
def event_participant_invitation_decline(
    request,
    participant_id,
):

    participant = get_object_or_404(
        EventParticipant,
        id=participant_id,
        user=request.user,
        status=EventParticipant.Status.INVITED,
    )


    if request.method == "POST":

        participant.delete()


    return redirect(
        "event_scheduler:event_list"
    )


# =========================================================
# Cancel participant invitation
# =========================================================

@login_required
def event_participant_invitation_cancel(
    request,
    event_id,
    participant_id,
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


    participant = get_object_or_404(
        EventParticipant,
        id=participant_id,
        event=event,
        status=EventParticipant.Status.INVITED,
    )


    if request.method == "POST":

        participant.delete()

        messages.success(
            request,
            "参加者への招待を取り消しました。",
        )


    return redirect(
        "event_scheduler:event_participants",
        event_id=event.id,
    )



# =========================================================
# Guest event detail with results
# =========================================================

def guest_event_detail(request, share_token):

    event = get_object_or_404(
        Event,
        share_token=share_token,
        is_archived=False,
    )

    session_key = f"event_guest_{event.pk}"
    guest_token = request.session.get(session_key)

    guest = None

    if guest_token:
        guest = EventGuestParticipant.objects.filter(
            event=event,
            edit_token=guest_token,
        ).first()

    has_answered = False

    if guest:

        if event.scheduling_mode == Event.SchedulingMode.DATE_ONLY:

            has_answered = EventDateVote.objects.filter(
                event_date__event=event,
                guest=guest,
            ).exists()

        elif event.scheduling_mode == Event.SchedulingMode.TIME_OPTIONS:

            has_answered = EventTimeOptionVote.objects.filter(
                event_date__event=event,
                guest=guest,
            ).exists()

        elif event.scheduling_mode == Event.SchedulingMode.START_TIMES:

            has_answered = EventStartTimeVote.objects.filter(
                start_time_option__event_date__event=event,
                guest=guest,
            ).exists()

        elif event.scheduling_mode == Event.SchedulingMode.FREE_INPUT:

            has_answered = EventDateResponse.objects.filter(
                event_date__event=event,
                guest=guest,
            ).exists()

    context = {
        "event": event,
        "guest": guest,
        "has_answered": has_answered,
        "result_rows": [],
        "top_result_rows": [],
        "duration_result_rows": [],
    }

    if has_answered:
        context.update(
            build_event_results(event)
        )

    return render(
        request,
        "event_scheduler/guest_event_detail.html",
        context,
    )


# =========================================================
# Guest event response
# All four scheduling modes + duration voting
# =========================================================

@require_http_methods(["GET", "POST"])
def guest_event_respond(request, share_token):

    event = get_object_or_404(
        Event,
        share_token=share_token,
        is_archived=False,
    )

    session_key = f"event_guest_{event.pk}"

    guest = None
    guest_token = request.session.get(session_key)

    if guest_token:
        guest = EventGuestParticipant.objects.filter(
            event=event,
            edit_token=guest_token,
        ).first()

    candidate_dates = list(
        event.candidate_dates.all().order_by("date", "id")
    )

    time_options = list(
        event.time_options.all().order_by("order", "id")
    )

    start_options = list(
        EventStartTimeOption.objects.filter(
            event_date__event=event,
        )
        .select_related("event_date")
        .order_by(
            "event_date__date",
            "start_time",
            "id",
        )
    )

    duration_options = list(
        event.duration_options.all().order_by(
            "minutes",
            "id",
        )
    )

    errors = []
    display_name = guest.display_name if guest else ""

    # =====================================================
    # Existing guest answers
    # =====================================================

    date_votes = {}
    time_votes = {}
    start_votes = {}
    free_responses = {}
    duration_votes = set()

    if guest:

        date_votes = {
            vote.event_date_id: vote.status
            for vote in EventDateVote.objects.filter(
                event_date__event=event,
                guest=guest,
            )
        }

        time_votes = {
            (
                vote.event_date_id,
                vote.time_option_id,
            ): vote.status
            for vote in EventTimeOptionVote.objects.filter(
                event_date__event=event,
                guest=guest,
            )
        }

        start_votes = {
            vote.start_time_option_id: vote.status
            for vote in EventStartTimeVote.objects.filter(
                start_time_option__event_date__event=event,
                guest=guest,
            )
        }

        free_responses = {
            response.event_date_id: response
            for response in EventDateResponse.objects.filter(
                event_date__event=event,
                guest=guest,
            ).prefetch_related("windows")
        }

        duration_votes = set(
            EventDurationVote.objects.filter(
                duration_option__event=event,
                guest=guest,
            ).values_list(
                "duration_option_id",
                flat=True,
            )
        )

    # =====================================================
    # Helpers
    # =====================================================

    def read_status(field_name):

        value = request.POST.get(
            field_name,
            "",
        )

        if value and value not in AvailabilityStatus.values:
            errors.append(
                "回答に不正な値が含まれています。"
            )
            return ""

        return value

    def normalize_time(value):

        value = (value or "").strip()

        if len(value) == 4 and value.isdigit():
            value = f"{value[:2]}:{value[2:]}"

        return value

    # =====================================================
    # POST validation
    # =====================================================

    posted_statuses = {}
    posted_free = {}
    posted_duration_ids = set()

    if request.method == "POST":

        display_name = request.POST.get(
            "display_name",
            "",
        ).strip()

        if not display_name:
            errors.append(
                "お名前を入力してください。"
            )

        if len(display_name) > 50:
            errors.append(
                "お名前は50文字以内にしてください。"
            )

        has_response = False

        # -------------------------------------------------
        # Mode 1: Date only
        # -------------------------------------------------

        if event.scheduling_mode == Event.SchedulingMode.DATE_ONLY:

            for candidate in candidate_dates:

                status = read_status(
                    f"date_status_{candidate.id}"
                )

                posted_statuses[candidate.id] = status

                if status:
                    has_response = True

        # -------------------------------------------------
        # Mode 2: Time options
        # -------------------------------------------------

        elif event.scheduling_mode == Event.SchedulingMode.TIME_OPTIONS:

            for candidate in candidate_dates:

                for option in time_options:

                    status = read_status(
                        f"time_option_status_{candidate.id}_{option.id}"
                    )

                    posted_statuses[
                        (candidate.id, option.id)
                    ] = status

                    if status:
                        has_response = True

        # -------------------------------------------------
        # Mode 3: Start times
        # -------------------------------------------------

        elif event.scheduling_mode == Event.SchedulingMode.START_TIMES:

            for option in start_options:

                status = read_status(
                    f"start_status_{option.id}"
                )

                posted_statuses[option.id] = status

                if status:
                    has_response = True

        # -------------------------------------------------
        # Mode 4: Free input
        # -------------------------------------------------

        elif event.scheduling_mode == Event.SchedulingMode.FREE_INPUT:

            for candidate in candidate_dates:

                response_type = request.POST.get(
                    f"response_type_{candidate.id}",
                    "",
                )

                note = request.POST.get(
                    f"note_{candidate.id}",
                    "",
                ).strip()

                if response_type and response_type not in (
                    EventDateResponse.ResponseType.values
                ):
                    errors.append(
                        f"{candidate.date} の回答が正しくありません。"
                    )
                    response_type = ""

                if len(note) > 255:
                    errors.append(
                        f"{candidate.date} のメモは255文字以内にしてください。"
                    )

                windows = []

                if response_type == (
                    EventDateResponse.ResponseType.PARTIAL
                ):

                    starts = request.POST.getlist(
                        f"free_start_{candidate.id}"
                    )

                    ends = request.POST.getlist(
                        f"free_end_{candidate.id}"
                    )

                    if len(starts) != len(ends) or len(starts) > 20:
                        errors.append(
                            f"{candidate.date} の時間入力が正しくありません。"
                        )

                    else:
                        for start, end in zip(starts, ends):

                            start = normalize_time(start)
                            end = normalize_time(end)

                            if not start and not end:
                                continue

                            parsed_start = parse_time(start)
                            parsed_end = parse_time(end)

                            if (
                                parsed_start is None
                                or parsed_end is None
                                or parsed_end <= parsed_start
                            ):
                                errors.append(
                                    f"{candidate.date} の時間帯を正しく入力してください。"
                                )
                                continue

                            windows.append(
                                (parsed_start, parsed_end)
                            )

                    if not windows:
                        errors.append(
                            f"{candidate.date} の空き時間を入力してください。"
                        )

                posted_free[candidate.id] = {
                    "response_type": response_type,
                    "note": note,
                    "windows": windows,
                }

                if response_type:
                    has_response = True

        else:
            errors.append(
                "未対応の日程調整方式です。"
            )

        # -------------------------------------------------
        # Duration voting
        # -------------------------------------------------

        if event.duration_mode == Event.DurationMode.VOTE:

            valid_duration_ids = {
                option.id for option in duration_options
            }

            for raw_id in request.POST.getlist(
                "duration_option"
            ):

                try:
                    option_id = int(raw_id)
                except (TypeError, ValueError):
                    errors.append(
                        "イベントの長さの回答が正しくありません。"
                    )
                    continue

                if option_id not in valid_duration_ids:
                    errors.append(
                        "存在しない長さの候補が含まれています。"
                    )
                    continue

                posted_duration_ids.add(option_id)

        if not has_response:
            errors.append(
                "少なくとも1つの候補に回答してください。"
            )

        # =================================================
        # Save everything atomically
        # =================================================

        if not errors:

            with transaction.atomic():

                if guest is None:

                    guest = EventGuestParticipant.objects.create(
                        event=event,
                        display_name=display_name,
                    )

                elif guest.display_name != display_name:

                    guest.display_name = display_name
                    guest.save(
                        update_fields=[
                            "display_name",
                            "updated_at",
                        ]
                    )

                # -----------------------------------------
                # Date only
                # -----------------------------------------

                if event.scheduling_mode == (
                    Event.SchedulingMode.DATE_ONLY
                ):

                    for candidate in candidate_dates:

                        status = posted_statuses[candidate.id]

                        if status:

                            EventDateVote.objects.update_or_create(
                                event_date=candidate,
                                guest=guest,
                                defaults={"status": status},
                            )

                        else:

                            EventDateVote.objects.filter(
                                event_date=candidate,
                                guest=guest,
                            ).delete()

                # -----------------------------------------
                # Time options
                # -----------------------------------------

                elif event.scheduling_mode == (
                    Event.SchedulingMode.TIME_OPTIONS
                ):

                    for candidate in candidate_dates:
                        for option in time_options:

                            status = posted_statuses[
                                (candidate.id, option.id)
                            ]

                            if status:

                                EventTimeOptionVote.objects.update_or_create(
                                    event_date=candidate,
                                    time_option=option,
                                    guest=guest,
                                    defaults={"status": status},
                                )

                            else:

                                EventTimeOptionVote.objects.filter(
                                    event_date=candidate,
                                    time_option=option,
                                    guest=guest,
                                ).delete()

                # -----------------------------------------
                # Start times
                # -----------------------------------------

                elif event.scheduling_mode == (
                    Event.SchedulingMode.START_TIMES
                ):

                    for option in start_options:

                        status = posted_statuses[option.id]

                        if status:

                            EventStartTimeVote.objects.update_or_create(
                                start_time_option=option,
                                guest=guest,
                                defaults={"status": status},
                            )

                        else:

                            EventStartTimeVote.objects.filter(
                                start_time_option=option,
                                guest=guest,
                            ).delete()

                # -----------------------------------------
                # Free input
                # -----------------------------------------

                elif event.scheduling_mode == (
                    Event.SchedulingMode.FREE_INPUT
                ):

                    for candidate in candidate_dates:

                        item = posted_free[candidate.id]

                        if not item["response_type"]:

                            EventDateResponse.objects.filter(
                                event_date=candidate,
                                guest=guest,
                            ).delete()

                            continue

                        response, created = (
                            EventDateResponse.objects.update_or_create(
                                event_date=candidate,
                                guest=guest,
                                defaults={
                                    "response_type":
                                        item["response_type"],
                                    "note": item["note"],
                                },
                            )
                        )

                        response.windows.all().delete()

                        if item["response_type"] == (
                            EventDateResponse.ResponseType.PARTIAL
                        ):

                            for start_time, end_time in item["windows"]:

                                AvailabilityWindow.objects.create(
                                    response=response,
                                    start_time=start_time,
                                    end_time=end_time,
                                )

                # -----------------------------------------
                # Duration
                # -----------------------------------------

                if event.duration_mode == (
                    Event.DurationMode.VOTE
                ):

                    EventDurationVote.objects.filter(
                        duration_option__event=event,
                        guest=guest,
                    ).delete()

                    EventDurationVote.objects.bulk_create([
                        EventDurationVote(
                            duration_option_id=option_id,
                            guest=guest,
                        )
                        for option_id in posted_duration_ids
                    ])

            # Only set session after successful save
            request.session[session_key] = str(
                guest.edit_token
            )

            messages.success(
                request,
                "回答を保存しました！",
            )

            return redirect(
                "event_scheduler:guest_event_detail",
                share_token=event.share_token,
            )

    # =====================================================
    # Build template data
    # =====================================================

    date_rows = []

    for candidate in candidate_dates:

        row = {
            "candidate": candidate,
        }

        # -------------------------------------------------
        # Date only
        # -------------------------------------------------

        if event.scheduling_mode == (
            Event.SchedulingMode.DATE_ONLY
        ):

            row["status"] = (
                request.POST.get(
                    f"date_status_{candidate.id}", ""
                )
                if request.method == "POST"
                else date_votes.get(candidate.id, "")
            )

        # -------------------------------------------------
        # Time options
        # -------------------------------------------------

        elif event.scheduling_mode == (
            Event.SchedulingMode.TIME_OPTIONS
        ):

            row["options"] = []

            for option in time_options:

                status = (
                    request.POST.get(
                        f"time_option_status_{candidate.id}_{option.id}",
                        "",
                    )
                    if request.method == "POST"
                    else time_votes.get(
                        (candidate.id, option.id),
                        "",
                    )
                )

                row["options"].append({
                    "option": option,
                    "status": status,
                })

        # -------------------------------------------------
        # Start times
        # -------------------------------------------------

        elif event.scheduling_mode == (
            Event.SchedulingMode.START_TIMES
        ):

            row["options"] = []

            for option in start_options:

                if option.event_date_id != candidate.id:
                    continue

                status = (
                    request.POST.get(
                        f"start_status_{option.id}", ""
                    )
                    if request.method == "POST"
                    else start_votes.get(option.id, "")
                )

                row["options"].append({
                    "option": option,
                    "status": status,
                })

        # -------------------------------------------------
        # Free input
        # -------------------------------------------------

        elif event.scheduling_mode == (
            Event.SchedulingMode.FREE_INPUT
        ):

            if request.method == "POST":

                row["response_type"] = request.POST.get(
                    f"response_type_{candidate.id}", ""
                )

                row["note"] = request.POST.get(
                    f"note_{candidate.id}", ""
                )

                starts = request.POST.getlist(
                    f"free_start_{candidate.id}"
                )

                ends = request.POST.getlist(
                    f"free_end_{candidate.id}"
                )

                row["windows"] = [
                    {
                        "start": normalize_time(start),
                        "end": normalize_time(end),
                    }
                    for start, end in zip(starts, ends)
                ]

            else:

                response = free_responses.get(candidate.id)

                row["response_type"] = (
                    response.response_type if response else ""
                )

                row["note"] = (
                    response.note if response else ""
                )

                row["windows"] = [
                    {
                        "start": window.start_time.strftime("%H:%M"),
                        "end": window.end_time.strftime("%H:%M"),
                    }
                    for window in (
                        response.windows.all() if response else []
                    )
                ]

            if not row["windows"]:
                row["windows"] = [
                    {"start": "", "end": ""}
                ]

        date_rows.append(row)

    selected_duration_option_ids = (
        posted_duration_ids
        if request.method == "POST"
        else duration_votes
    )

    return render(
        request,
        "event_scheduler/guest_event_respond.html",
        {
            "event": event,
            "guest": guest,
            "display_name": display_name,
            "date_rows": date_rows,
            "duration_options": duration_options,
            "selected_duration_option_ids":
                selected_duration_option_ids,
            "errors": errors,
            "can_add_date": event.allow_participant_date_addition,

            "can_add_time_option": (
                event.scheduling_mode == Event.SchedulingMode.TIME_OPTIONS
                and event.allow_participant_time_option_addition
            ),

            "can_add_duration": (
                event.duration_mode == Event.DurationMode.VOTE
                and event.allow_participant_duration_addition
            ),
        },
        
    )


# =========================================================
# Guest: add event candidates
# =========================================================

@require_http_methods(["POST"])
def guest_event_add_candidate(request, share_token):

    event = get_object_or_404(
        Event,
        share_token=share_token,
        is_archived=False,
    )

    redirect_kwargs = {
        "share_token": event.share_token,
    }

    def back():
        return redirect(
            "event_scheduler:guest_event_respond",
            **redirect_kwargs,
        )

    # -----------------------------------------------------
    # Identify guest
    # -----------------------------------------------------

    session_key = f"event_guest_{event.pk}"
    guest_token = request.session.get(session_key)

    guest = None

    if guest_token:
        guest = EventGuestParticipant.objects.filter(
            event=event,
            edit_token=guest_token,
        ).first()


    # -----------------------------------------------------
    # Permissions
    # -----------------------------------------------------

    can_add_date = event.allow_participant_date_addition

    can_add_time_option = (
        event.scheduling_mode == Event.SchedulingMode.TIME_OPTIONS
        and event.allow_participant_time_option_addition
    )

    can_add_duration = (
        event.duration_mode == Event.DurationMode.VOTE
        and event.allow_participant_duration_addition
    )

    action = request.POST.get("action", "")

    # -----------------------------------------------------
    # Add date / start time
    # -----------------------------------------------------

    if action == "add_candidate_date":

        if not can_add_date:
            return HttpResponseForbidden(
                "候補日の追加は許可されていません。"
            )

        new_date = parse_date(
            request.POST.get("new_candidate_date", "")
        )

        if new_date is None:
            messages.error(request, "正しい日付を入力してください。")
            return back()

        if event.scheduling_mode == Event.SchedulingMode.START_TIMES:

            raw_time = request.POST.get(
                "new_candidate_start_time", ""
            ).strip()

            if len(raw_time) == 4 and raw_time.isdigit():
                raw_time = f"{raw_time[:2]}:{raw_time[2:]}"

            start_time = parse_time(raw_time)

            if start_time is None:
                messages.error(
                    request,
                    "正しい開始時間を入力してください。",
                )
                return back()

            with transaction.atomic():

                candidate, _ = EventDate.objects.get_or_create(
                    event=event,
                    date=new_date,
                    defaults={"created_by": None},
                )

                if EventStartTimeOption.objects.filter(
                    event_date=candidate,
                    start_time=start_time,
                ).exists():

                    messages.warning(
                        request,
                        "この日時はすでに候補にあります。",
                    )
                    return back()

                EventStartTimeOption.objects.create(
                    event_date=candidate,
                    start_time=start_time,
                )

        else:

            if EventDate.objects.filter(
                event=event,
                date=new_date,
            ).exists():

                messages.warning(
                    request,
                    "この日はすでに候補にあります。",
                )
                return back()

            EventDate.objects.create(
                event=event,
                date=new_date,
                created_by=None,
            )

        messages.success(
            request,
            "候補を追加しました。",
        )
        return back()

    # -----------------------------------------------------
    # Add time option
    # -----------------------------------------------------

    if action == "add_time_option":

        if not can_add_time_option:
            return HttpResponseForbidden(
                "時間帯の追加は許可されていません。"
            )

        label = request.POST.get(
            "new_time_option_label", ""
        ).strip()

        start_value = request.POST.get(
            "new_time_option_start", ""
        ).strip()

        end_value = request.POST.get(
            "new_time_option_end", ""
        ).strip()

        if not label or len(label) > 100:
            messages.error(
                request,
                "時間帯の名前を1〜100文字で入力してください。",
            )
            return back()

        start_time = parse_time(start_value) if start_value else None
        end_time = parse_time(end_value) if end_value else None

        if (start_value and start_time is None) or (
            end_value and end_time is None
        ):
            messages.error(
                request,
                "時間の形式が正しくありません。",
            )
            return back()

        if (start_time is None) != (end_time is None):
            messages.error(
                request,
                "開始時間と終了時間は両方入力してください。",
            )
            return back()

        if start_time and end_time <= start_time:
            messages.error(
                request,
                "終了時間は開始時間より後にしてください。",
            )
            return back()

        if EventTimeOption.objects.filter(
            event=event,
            label__iexact=label,
            start_time=start_time,
            end_time=end_time,
        ).exists():

            messages.warning(
                request,
                "同じ時間帯がすでにあります。",
            )
            return back()

        next_order = (
            EventTimeOption.objects.filter(
                event=event,
            ).aggregate(
                max_order=Max("order")
            )["max_order"]
        )

        EventTimeOption.objects.create(
            event=event,
            label=label,
            start_time=start_time,
            end_time=end_time,
            order=(next_order + 1 if next_order is not None else 0),
        )

        messages.success(
            request,
            "時間帯を追加しました。",
        )
        return back()

    # -----------------------------------------------------
    # Add duration
    # -----------------------------------------------------

    if action == "add_duration_option":

        if not can_add_duration:
            return HttpResponseForbidden(
                "イベントの長さの追加は許可されていません。"
            )

        try:
            minutes = int(
                request.POST.get("new_duration_minutes", "")
            )
        except (TypeError, ValueError):
            messages.error(
                request,
                "正しい長さを入力してください。",
            )
            return back()

        if minutes < 15 or minutes > 1440 or minutes % 15 != 0:
            messages.error(
                request,
                "15〜1440分の範囲で15分刻みで入力してください。",
            )
            return back()

        option, created = EventDurationOption.objects.get_or_create(
            event=event,
            minutes=minutes,
        )

        if created:
            messages.success(
                request,
                "長さの候補を追加しました。",
            )
        else:
            messages.warning(
                request,
                "この長さはすでに候補にあります。",
            )

        return back()

    return HttpResponseBadRequest(
        "不正な操作です。"
    )


# =========================================================
# Edit event settings
# =========================================================

@login_required
@require_http_methods(["GET", "POST"])
def event_settings_edit(request, event_id):

    event = get_object_or_404(
        Event,
        pk=event_id,
        is_archived=False,
    )

    # Only event administrators can edit settings
    if not event.can_manage(request.user):

        return HttpResponseForbidden(
            "イベント設定を変更する権限がありません。"
        )

    if request.method == "POST":

        form = EventSettingsForm(
            request.POST,
            instance=event,
        )

        if form.is_valid():

            form.save()

            messages.success(
                request,
                "イベント設定を更新しました。",
            )

            return redirect(
                "event_scheduler:event_detail",
                event_id=event.id,
            )

    else:

        form = EventSettingsForm(
            instance=event,
        )

    return render(
        request,
        "event_scheduler/event_settings_edit.html",
        {
            "event": event,
            "form": form,
        },
    )

from django.contrib.auth.views import redirect_to_login


def event_detail_entry(request, event_id):

    event = get_object_or_404(
        Event,
        pk=event_id,
    )

    # ログイン済みなら既存の詳細画面
    if request.user.is_authenticated:
        return event_detail(request, event_id)

    # 未ログインかつ公開イベントならゲスト画面
    if event.is_public and not event.is_archived:
        return redirect(
            "event_scheduler:guest_event_detail",
            share_token=event.share_token,
        )

    # 非公開イベントはログインが必要
    return redirect_to_login(request.get_full_path())