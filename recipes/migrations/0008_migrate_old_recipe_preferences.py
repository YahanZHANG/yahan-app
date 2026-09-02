from django.db import migrations


def migrate_preferences(apps, schema_editor):

    RecipePreference = apps.get_model(
        "recipes",
        "RecipePreference",
    )

    RecipePreference.objects.filter(
        preference="favorite",
        rating__isnull=True,
    ).update(
        rating=5,
    )

    RecipePreference.objects.filter(
        preference="dislike",
        rating__isnull=True,
    ).update(
        rating=1,
    )


class Migration(migrations.Migration):

    dependencies = [
        (
            "recipes",
            "0007_recipepreference_make_ahead_override_and_more",
        ),
    ]

    operations = [
        migrations.RunPython(
            migrate_preferences,
            migrations.RunPython.noop,
        ),
    ]