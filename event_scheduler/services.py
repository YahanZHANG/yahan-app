from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

from .models import (
    EventDateResponse,
    EventParticipant,
)


def make_local_datetime(
    date_value,
    time_value,
):

    dt = datetime.combine(
        date_value,
        time_value,
    )

    if settings.USE_TZ:
        return timezone.make_aware(
            dt,
            timezone.get_current_timezone(),
        )

    return dt


def get_recommended_slots(
    event,
    step_minutes=30,
    limit=5,
):

    participants = list(
        EventParticipant.objects.filter(
            event=event,
            status=EventParticipant.Status.JOINED,
        ).select_related(
            "user",
        )
    )

    participant_ids = [
        participant.user_id
        for participant in participants
    ]

    participant_count = len(participants)

    if participant_count == 0:
        return []

    duration = timedelta(
        minutes=event.duration_minutes,
    )

    step = timedelta(
        minutes=step_minutes,
    )

    recommendations = []

    candidate_dates = event.candidate_dates.all()

    for event_date in candidate_dates:

        responses = (
            EventDateResponse.objects
            .filter(
                event_date=event_date,
                user_id__in=participant_ids,
            )
            .select_related(
                "user",
            )
            .prefetch_related(
                "windows",
            )
        )

        response_map = {
            response.user_id: response
            for response in responses
        }

        day_start = make_local_datetime(
            event_date.date,
            event.day_start_time,
        )

        day_end = make_local_datetime(
            event_date.date,
            event.day_end_time,
        )

        slot_start = day_start

        while slot_start + duration <= day_end:

            slot_end = (
                slot_start
                + duration
            )

            available_users = []
            unavailable_users = []
            unanswered_users = []

            for participant in participants:

                user = participant.user

                response = response_map.get(
                    user.id
                )

                if response is None:

                    unanswered_users.append(
                        user
                    )

                    continue

                if (
                    response.response_type
                    == EventDateResponse.ResponseType.UNAVAILABLE
                ):

                    unavailable_users.append(
                        user
                    )

                    continue

                if (
                    response.response_type
                    == EventDateResponse.ResponseType.ALL_DAY
                ):

                    available_users.append(
                        user
                    )

                    continue

                if (
                    response.response_type
                    == EventDateResponse.ResponseType.PARTIAL
                ):

                    is_available = False

                    slot_start_time = (
                        slot_start.time()
                    )

                    slot_end_time = (
                        slot_end.time()
                    )

                    for window in response.windows.all():

                        if (
                            window.start_time
                            <= slot_start_time
                            and
                            window.end_time
                            >= slot_end_time
                        ):

                            is_available = True
                            break

                    if is_available:

                        available_users.append(
                            user
                        )

                    else:

                        unavailable_users.append(
                            user
                        )

            recommendations.append(
                {
                    "event_date": event_date,
                    "start": slot_start,
                    "end": slot_end,
                    "available_count": len(
                        available_users
                    ),
                    "participant_count": (
                        participant_count
                    ),
                    "unavailable_count": len(
                        unavailable_users
                    ),
                    "unanswered_count": len(
                        unanswered_users
                    ),
                    "available_users": (
                        available_users
                    ),
                    "unavailable_users": (
                        unavailable_users
                    ),
                    "unanswered_users": (
                        unanswered_users
                    ),
                    "everyone_available": (
                        len(available_users)
                        == participant_count
                    ),
                }
            )

            slot_start += step

    recommendations.sort(
        key=lambda slot: (
            -slot["available_count"],
            slot["unavailable_count"],
            slot["unanswered_count"],
            slot["start"],
        )
    )

    return recommendations[:limit]