from django.db import migrations


def remove_sayaingen(apps, schema_editor):
    # 管理画面で消した「さやいんげん → いんげん」の代用品が、デプロイ時の取り込みで戻っていたら消す
    Substitute = apps.get_model("washoku", "Substitute")
    Substitute.objects.filter(original_name="さやいんげん", substitute__name="いんげん").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("washoku", "0042_home_photos"),
    ]

    operations = [
        migrations.RunPython(remove_sayaingen, migrations.RunPython.noop),
    ]
