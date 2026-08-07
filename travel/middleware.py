from urllib.parse import urlencode

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse


class TravelAccessMiddleware:
    """
    travel_usersグループの利用者と管理者だけ、
    旅行管理アプリアプリへアクセスできるようにする。
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith("/travel/"):
            return self.get_response(request)

        if not request.user.is_authenticated:
            login_url = reverse("login")
            query_string = urlencode(
                {
                    "next": request.get_full_path(),
                }
            )

            return redirect(
                f"{login_url}?{query_string}"
            )

        can_use_travel = (
            request.user.is_superuser
            or request.user.groups.filter(
                name="travel_users"
            ).exists()
        )

        if not can_use_travel:
            messages.error(
                request,
                "このアカウントでは旅行管理アプリアプリを利用できない。",
            )

            return redirect("portal:home")

        return self.get_response(request)