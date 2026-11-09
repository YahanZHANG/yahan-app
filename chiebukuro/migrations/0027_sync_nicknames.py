"""
2026-11-09
これまでの投稿の名前を、今のニックネームにそろえる (名前を変えても古い名前のままだった投稿)
"""

from django.conf import settings
from django.db import migrations


TABLES = [
    ("Question", "author"),
    ("Answer", "author"),
    ("Post", "author"),
    ("PostReply", "author"),
    ("Item", "owner"),
    ("Notice", "owner"),
    ("ItemRequest", "requester"),
]


def forwards(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    UserProfile = apps.get_model("core", "UserProfile")
    nicknames = {
        user_id: (nickname or "").strip()
        for user_id, nickname in UserProfile.objects.values_list("user_id", "nickname")
    }
    for model_name, field in TABLES:
        model = apps.get_model("chiebukuro", model_name)
        rows = model.objects.filter(**{f"{field}__isnull": False})
        if model_name == "Question":
            rows = rows.exclude(source="staff")
        for user_id in set(rows.values_list(f"{field}_id", flat=True)):
            name = nicknames.get(user_id) or User.objects.filter(pk=user_id).values_list("username", flat=True).first() or ""
            if name:
                rows.filter(**{f"{field}_id": user_id}).exclude(nickname=name[:30]).update(nickname=name[:30])


class Migration(migrations.Migration):

    dependencies = [
        ("chiebukuro", "0026_staff_answers"),
        ("core", "0027_userprofile_theme_preference"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
