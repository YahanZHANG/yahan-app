from .i18n import get_ui


def vaccination_ui(request):
    language_code = "ja"

    if request.user.is_authenticated:
        try:
            language_code = (
                request.user
                .vaccination_settings
                .ui_language
                or "ja"
            )
        except Exception:
            pass

    return {
        "vac_ui": get_ui(language_code),
        "vac_language": language_code,
    }