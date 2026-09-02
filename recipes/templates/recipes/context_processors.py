from .models import RecipeUserSettings


def recipe_ui_settings(request):

    font_size = "medium"


    if request.user.is_authenticated:

        settings_obj = (
            RecipeUserSettings.objects
            .filter(
                user=request.user,
            )
            .first()
        )

        if settings_obj:

            font_size = (
                settings_obj.font_size
            )


    return {
        "recipe_font_size":
            font_size,
    }