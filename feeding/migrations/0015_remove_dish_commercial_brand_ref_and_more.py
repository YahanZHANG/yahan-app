from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        (
            "feeding",
            "0014_migrate_commercial_brands",
        ),
    ]

    operations = [
        migrations.RemoveField(
            model_name="dish",
            name="commercial_brand",
        ),
        migrations.RenameField(
            model_name="dish",
            old_name="commercial_brand_ref",
            new_name="commercial_brand",
        ),
    ]