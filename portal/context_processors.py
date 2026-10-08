from django.db.utils import (
    OperationalError,
    ProgrammingError,
)

from news.models import (
    NewsFeedback,
    SupportRequest,
)

from portal.models import (
    AppAccessRequest,
)


def admin_attention_counts(
    request,
):

    if (
        not request.user.is_authenticated
        or not request.user.is_staff
    ):

        return {}

    try:

        feedback_count = (
            NewsFeedback.objects
            .filter(
                is_read=False
            )
            .count()
        )

        support_count = (
            SupportRequest.objects
            .filter(
                is_read=False
            )
            .count()
        )

        access_count = (
            AppAccessRequest.objects
            .filter(
                status=(
                    AppAccessRequest
                    .Status
                    .PENDING
                )
            )
            .count()
        )

    except (
        OperationalError,
        ProgrammingError,
    ):

        return {}

    total_count = (
        feedback_count
        + support_count
        + access_count
    )

    return {
        "admin_attention": {
            "feedback": feedback_count,
            "support": support_count,
            "access": access_count,
            "total": total_count,
        }
    }