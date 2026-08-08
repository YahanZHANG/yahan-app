from .models import TravelGroup


def current_travel_group(request):
    if not request.user.is_authenticated:
        return {
            "global_current_travel_group": None,
        }

    travel_groups = (
        TravelGroup.objects
        .filter(members=request.user)
        .exclude(archived_by=request.user)
        .distinct()
    )

    current_group_id = request.session.get(
        "current_travel_group_id"
    )

    current_group = None

    if current_group_id:
        current_group = travel_groups.filter(
            id=current_group_id
        ).first()

    if current_group is None:
        current_group = travel_groups.first()

    return {
        "global_current_travel_group": current_group,
    }