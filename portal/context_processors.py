
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

from outings.models import (
    Event,
)


# =========================================================
# Admin Attention Counts
# =========================================================

def admin_attention_counts(request):

    # Admin以外は集計しない
    if (
        not request.user.is_authenticated
        or not request.user.is_staff
    ):
        return {}

    try:

        # =================================================
        # Swiss News: Feedback
        # =================================================

        feedback_count = (
            NewsFeedback.objects
            .filter(
                is_read=False
            )
            .count()
        )

        # =================================================
        # Swiss News: Support requests
        # =================================================

        support_count = (
            SupportRequest.objects
            .filter(
                is_read=False
            )
            .count()
        )

        # =================================================
        # Portal: App access requests
        # =================================================

        access_count = (
            AppAccessRequest.objects
            .filter(
                status=AppAccessRequest.Status.PENDING
            )
            .count()
        )

        # =================================================
        # Outings: Pending event submissions
        # =================================================

        outings_count = (
            Event.objects
            .filter(
                status=Event.Status.PENDING
            )
            .count()
        )

    except (
        OperationalError,
        ProgrammingError,
    ):
        # マイグレーション前など、
        # テーブルが存在しない場合に備える
        return {}

    # =====================================================
    # Total attention count
    # =====================================================

    total_count = (
        feedback_count
        + support_count
        + access_count
        + outings_count
    )

    return {
        "admin_attention": {
            "feedback": feedback_count,
            "support": support_count,
            "access": access_count,
            "outings": outings_count,
            "total": total_count,
        }
    }
