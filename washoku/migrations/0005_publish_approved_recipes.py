from django.db import migrations


def publish(apps, schema_editor):
    # 2026-10-20: 最初に用意した料理はすべて承認済み。会員の投稿は対象外。
    Recipe = apps.get_model("washoku", "Recipe")
    Recipe.objects.filter(status="draft").exclude(origin="member").update(status="published")


class Migration(migrations.Migration):

    dependencies = [
        ("washoku", "0004_member_recipes_and_store_location"),
    ]

    operations = [
        migrations.RunPython(publish, migrations.RunPython.noop),
    ]
