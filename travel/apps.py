from django.apps import AppConfig


class TravelConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"

    # Python上の新しいアプリ名
    name = "travel"

    # 既存のcoreマイグレーションとの互換性を維持する
    label = "core"

    verbose_name = "家族旅行"