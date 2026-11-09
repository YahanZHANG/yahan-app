from django.apps import AppConfig


class ChiebukuroConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "chiebukuro"
    verbose_name = "スイス掲示板 (掲示板)"

    def ready(self):
        from django.db.models.signals import post_save

        from travel.models import UserProfile

        post_save.connect(rename_on_profile_save, sender=UserProfile, dispatch_uid="chiebukuro_rename")


def rename_on_profile_save(sender, instance, update_fields=None, raw=False, **kwargs):
    """Yapp のどこでニックネームを変えても、掲示板のこれまでの投稿を新しい名前にする"""

    if raw or (update_fields is not None and "nickname" not in update_fields):
        return
    from .services import rename_member_content

    rename_member_content(instance.user, instance.display_name)
