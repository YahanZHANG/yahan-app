from django.apps import AppConfig


class TravelConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"

    name = "travel"
    label = "core"

    verbose_name = "旅行管理アプリ"

    def ready(self):
        import travel.signals