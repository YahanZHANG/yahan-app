from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from feeding.models import BabyMembership
from travel.models import UserProfile

from .forms import NicknameForm


@login_required
def home(request):

    profile, _ = UserProfile.objects.get_or_create(
        user=request.user
    )

    can_use_feeding = (
        request.user.is_superuser
        or BabyMembership.objects.filter(
            user=request.user
        ).exists()
    )

    if request.method == "POST":

        nickname_form = NicknameForm(
            request.POST,
            instance=profile,
        )

        if nickname_form.is_valid():

            nickname_form.save()

            messages.success(
                request,
                "ニックネームを保存しました。",
            )

            return redirect(
                "portal:home"
            )

    else:

        nickname_form = NicknameForm(
            instance=profile
        )

    context = {
        "can_use_feeding": can_use_feeding,
        "profile": profile,
        "nickname_form": nickname_form,
    }

    return render(
        request,
        "portal/home.html",
        context,
    )