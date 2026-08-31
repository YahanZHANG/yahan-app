from .i18n import get_ui
from .permissions import (
    user_can_edit_child,
    user_can_manage_child,
    user_can_view_child,
)


def vaccination_ui(request):
    language_code = "ja"

    can_edit_current_child = False
    can_manage_current_child = False

    if request.user.is_authenticated:

        try:
            settings_obj = (
                request.user
                .vaccination_settings
            )

            language_code = (
                settings_obj.ui_language
                or "ja"
            )

            child = (
                settings_obj.active_child
            )

            if (
                child
                and
                user_can_view_child(
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

        except Exception:
            pass

    return {
        "vac_ui": get_ui(
            language_code
        ),
        "vac_language": (
            language_code
        ),
        "can_edit_current_child": (
            can_edit_current_child
        ),
        "can_manage_current_child": (
            can_manage_current_child
        ),
    }