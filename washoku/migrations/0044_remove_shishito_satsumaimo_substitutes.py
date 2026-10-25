from django.db import migrations


def remove_substitutes(apps, schema_editor):
    # 「代わり」から外した「ししとう」「さつまいも」の代用品 (デプロイ時の取り込みで戻っていたら消す)
    Substitute = apps.get_model("washoku", "Substitute")
    Substitute.objects.filter(original_name__in=["ししとう", "さつまいも"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("washoku", "0043_remove_sayaingen_substitute"),
    ]

    operations = [
        migrations.RunPython(remove_substitutes, migrations.RunPython.noop),
    ]
