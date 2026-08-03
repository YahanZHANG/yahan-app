from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from feeding.models import BabyMembership


@login_required
def home(request):
    can_use_travel = (
        request.user.is_superuser
        or request.user.groups.filter(
            name="travel_users"
        ).exists()
    )

    can_use_feeding = (
        request.user.is_superuser
        or BabyMembership.objects.filter(
            user=request.user
        ).exists()
    )

    context = {
        "can_use_travel": can_use_travel,
        "can_use_feeding": can_use_feeding,
    }

    return render(
        request,
        "portal/home.html",
        context,
    )