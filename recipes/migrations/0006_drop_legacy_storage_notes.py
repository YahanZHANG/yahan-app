from django.db import migrations


def drop_legacy_storage_notes(apps, schema_editor):

    table_name = "recipes_recipe"
    column_name = "storage_notes"

    # 実際のDBにstorage_notesが残っているか確認
    with schema_editor.connection.cursor() as cursor:

        columns = {
            column.name
            for column
            in schema_editor.connection.introspection.get_table_description(
                cursor,
                table_name,
            )
        }


    # すでに消えている環境では何もしない
    if column_name not in columns:
        return


    # DBから古い列だけ削除
    schema_editor.execute(
        f"ALTER TABLE "
        f"{schema_editor.quote_name(table_name)} "
        f"DROP COLUMN "
        f"{schema_editor.quote_name(column_name)}"
    )


class Migration(migrations.Migration):

    dependencies = [
        (
            "recipes",
            "0005_recipe_is_make_ahead_recipe_storage_notes",
        ),
    ]

    operations = [
        migrations.RunPython(
            drop_legacy_storage_notes,
            migrations.RunPython.noop,
        ),
    ]