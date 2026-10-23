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


TICINO_URL_PART = "_onigiri-tofu-kabocha"


def remove_ticino_link(apps, schema_editor):
    """
    要点を書かないままの swissinfo のリンク (下書き) を消す。元データからも外したので、もう戻らない。
    """

    Post = apps.get_model("washoku", "Post")

    Post.objects.filter(kind="link", url__contains=TICINO_URL_PART).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("washoku", "0022_ingredient_photo_auto_tried"),
    ]

    operations = [
        migrations.RunPython(remove_auto_photos, migrations.RunPython.noop),
        migrations.RunPython(remove_ticino_link, migrations.RunPython.noop),
    ]
