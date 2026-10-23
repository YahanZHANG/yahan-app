from django.db import migrations


def remove_auto_photos(apps, schema_editor):
    """
    起動時に自動で付けた Wikimedia の写真は合わないものばかりだったので外す。
    (Wikimedia の画像へのリンクだけなので、Cloudinary には何も残っていない)
    """

    Ingredient = apps.get_model("washoku", "Ingredient")

    Ingredient.objects.filter(
        photo_auto_tried=True,
        photo_url__startswith="https://upload.wikimedia.org/",
    ).update(photo_url="", photo_credit="", photo_source="")


class Migration(migrations.Migration):

    dependencies = [
        ("washoku", "0022_ingredient_photo_auto_tried"),
    ]

    operations = [
        migrations.RunPython(remove_auto_photos, migrations.RunPython.noop),
    ]
