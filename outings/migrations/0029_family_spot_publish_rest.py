"""Publish the remaining 子連れスポット (Taro's OK, 2026-11-07), now that each has a checked introduction."""

import datetime

from django.db import migrations


def forwards(apps, schema_editor):
    FamilySpot = apps.get_model("outings", "FamilySpot")
    FamilySpot.objects.filter(status="draft").update(status="published", checked_on=datetime.date(2026, 11, 7))


class Migration(migrations.Migration):
    dependencies = [("outings", "0028_family_spot_fixes")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
