
# =========================================================
# Yapp theme context processor
# =========================================================

from travel.models import UserProfile


def yapp_theme(request):

    theme = "system"

    if request.user.is_authenticated:

        profile = UserProfile.objects.filter(
            user=request.user
        ).only(
            "theme_preference"
        ).first()

        if profile is not None:

            theme = profile.theme_preference

    if theme not in {
        "light",
        "dark",
        "system",
    }:
        theme = "system"

    return {
        "yapp_theme": theme,
    }
