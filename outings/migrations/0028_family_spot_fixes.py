"""Fixes from Taro's check of the 子連れスポット (2026-11-07)."""

from django.db import migrations

OLD_MUSEUM = "Zoologisches Museum der Universität Zürich"
NEW_MUSEUM = "Naturhistorisches Museum der Universität Zürich"


def forwards(apps, schema_editor):
    FamilySpot = apps.get_model("outings", "FamilySpot")
    FamilySpot.objects.filter(name="Glasi Hergiswil").update(open_sunday=False)  # closed on Sundays
    FamilySpot.objects.filter(name="Bächlihof").update(season="year")  # open all year
    FamilySpot.objects.filter(name=OLD_MUSEUM).update(name=NEW_MUSEUM, name_ja="チューリッヒ大学 自然史博物館")


def backwards(apps, schema_editor):
    FamilySpot = apps.get_model("outings", "FamilySpot")
    FamilySpot.objects.filter(name=NEW_MUSEUM).update(name=OLD_MUSEUM, name_ja="チューリッヒ大学 動物博物館")


class Migration(migrations.Migration):
    dependencies = [("outings", "0027_family_spot_intro")]
    operations = [migrations.RunPython(forwards, backwards)]
