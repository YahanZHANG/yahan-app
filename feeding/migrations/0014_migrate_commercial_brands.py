from django.db import migrations


def migrate_brands_forward(
    apps,
    schema_editor,
):
    Dish = apps.get_model(
        "feeding",
        "Dish",
    )

    CommercialBrand = apps.get_model(
        "feeding",
        "CommercialBrand",
    )

    hipp, _ = CommercialBrand.objects.get_or_create(
        name="HiPP",
        defaults={
            "display_order": 10,
            "is_active": True,
        },
    )

    holle, _ = CommercialBrand.objects.get_or_create(
        name="Holle",
        defaults={
            "display_order": 20,
            "is_active": True,
        },
    )

    brand_map = {
        "hipp": hipp,
        "HiPP": hipp,
        "holle": holle,
        "Holle": holle,
    }

    for dish in Dish.objects.filter(
        is_commercial_product=True,
    ):
        brand = brand_map.get(
            dish.commercial_brand
        )

        if brand is None:
            continue

        dish.commercial_brand_ref = brand

        dish.save(
            update_fields=[
                "commercial_brand_ref",
            ]
        )


def migrate_brands_backward(
    apps,
    schema_editor,
):
    Dish = apps.get_model(
        "feeding",
        "Dish",
    )

    for dish in Dish.objects.exclude(
        commercial_brand_ref=None,
    ):
        brand_name = (
            dish.commercial_brand_ref.name
        )

        if brand_name == "HiPP":
            dish.commercial_brand = "hipp"

        elif brand_name == "Holle":
            dish.commercial_brand = "holle"

        else:
            dish.commercial_brand = (
                brand_name.lower()
            )

        dish.save(
            update_fields=[
                "commercial_brand",
            ]
        )


class Migration(migrations.Migration):

    dependencies = [
        (
            "feeding",
            "0013_commercialbrand_alter_dish_commercial_brand_and_more",
        ),
    ]

    operations = [
        migrations.RunPython(
            migrate_brands_forward,
            migrate_brands_backward,
        ),
    ]