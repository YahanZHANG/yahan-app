from django.db import migrations


def activate_unverified_signups(apps, schema_editor):
    """
    確認メールが届かず（迷惑メール）止まっていたアカウントを使えるようにする。
    一度もログインしていない一般登録ユーザーだけが対象。
    """

    User = apps.get_model("auth", "User")

    User.objects.filter(
        groups__name="public_users",
        is_active=False,
        last_login__isnull=True,
    ).update(is_active=True)


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("portal", "0003_appaccessrequest"),
    ]

    operations = [
        migrations.RunPython(
            activate_unverified_signups,
            migrations.RunPython.noop,
        ),
    ]
