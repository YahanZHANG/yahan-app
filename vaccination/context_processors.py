from .i18n import get_ui
from .models import VaccinationSettings
from .permissions import (
    user_can_edit_child,
    user_can_manage_child,
    user_can_view_child,
)


def vaccination_ui(request):
    """
    Vaccination app-wide template context.

    Provides:
    - UI translations
    - current UI language
    - font size
    - permission information for the active child
    """

    language_code = "ja"
    font_size = VaccinationSettings.FONT_SIZE_SMALL

    can_edit_current_child = False
    can_manage_current_child = False

    if request.user.is_authenticated:

        try:
            settings_obj = request.user.vaccination_settings

        except VaccinationSettings.DoesNotExist:
            settings_obj = None


        if settings_obj:

            # -------------------------------------------------
            # UI language
            # -------------------------------------------------

            language_code = (
                settings_obj.ui_language
                or "ja"
            )


            # -------------------------------------------------
            # Font size
            # -------------------------------------------------

            font_size = (
                settings_obj.font_size
                or VaccinationSettings.FONT_SIZE_SMALL
            )


            # -------------------------------------------------
            # Active child permissions
            # -------------------------------------------------

            child = settings_obj.active_child

            if (
                child
                and user_can_view_child(
                    request.user,
                    child,
                )
            ):

                can_edit_current_child = (
                    user_can_edit_child(
                        request.user,
                        child,
                    )
                )

                can_manage_current_child = (
                    user_can_manage_child(
                        request.user,
                        child,
                    )
                )


    return {
        "vac_ui": get_ui(language_code),
        "vac_language": language_code,

        "vac_font_size": font_size,

        "can_edit_current_child": can_edit_current_child,
        "can_manage_current_child": can_manage_current_child,
    }