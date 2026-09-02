import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from recipes.models import (
    Appliance,
    Ingredient,
    MoodTag,
    NutritionTag,
    Recipe,
    RecipeIngredient,
)


class Command(BaseCommand):
    help = "recipes/data/recipes.json からレシピを一括登録する"


    @transaction.atomic
    def handle(self, *args, **options):

        file_path = (
            Path(__file__)
            .resolve()
            .parents[2]
            / "data"
            / "recipes.json"
        )


        if not file_path.exists():
            self.stderr.write(
                self.style.ERROR(
                    f"ファイルが見つからない: {file_path}"
                )
            )
            return


        with file_path.open(
            "r",
            encoding="utf-8",
        ) as file:

            recipes_data = json.load(file)


        created_count = 0
        updated_count = 0


        for recipe_data in recipes_data:

            recipe_name = recipe_data["name"]

            appliance_type = recipe_data[
                "appliance_type"
            ]


            appliance = (
                Appliance.objects
                .filter(
                    appliance_type=appliance_type,
                )
                .first()
            )


            if not appliance:

                self.stderr.write(
                    self.style.WARNING(
                        f"{recipe_name}: "
                        f"調理家電 {appliance_type} "
                        "が登録されていないためスキップ"
                    )
                )

                continue


            recipe_defaults = {
                "category": recipe_data.get(
                    "category",
                    "other",
                ),

                "cooking_mode": recipe_data.get(
                    "cooking_mode",
                    "auto",
                ),

                "cooking_time_minutes":
                    recipe_data.get(
                        "cooking_time_minutes"
                    ),

                "servings":
                    recipe_data.get(
                        "servings"
                    ),

                "menu_number":
                    recipe_data.get(
                        "menu_number",
                        "",
                    ),

                "appliance_operation":
                    recipe_data.get(
                        "appliance_operation",
                        "",
                    ),

                "preparation":
                    recipe_data.get(
                        "preparation",
                        "",
                    ),

                "notes":
                    recipe_data.get(
                        "notes",
                        "",
                    ),

                "source_name":
                    recipe_data.get(
                        "source_name",
                        "",
                    ),

                "source_url":
                    recipe_data.get(
                        "source_url",
                        "",
                    ),

                "is_official":
                    recipe_data.get(
                        "is_official",
                        False,
                    ),

                "verified_for_model":
                    recipe_data.get(
                        "verified_for_model",
                        False,
                    ),

                "switzerland_score":
                    recipe_data.get(
                        "switzerland_score",
                        5,
                    ),

                "is_active":
                    recipe_data.get(
                        "is_active",
                        True,
                    ),
            }


            # 同じ料理名でも、
            # ホットクックとシェフドラムは別レシピとして扱う
            recipe, created = (
                Recipe.objects.update_or_create(
                    name=recipe_name,
                    appliance=appliance,
                    defaults=recipe_defaults,
                )
            )


            if created:
                created_count += 1
            else:
                updated_count += 1


            # =====================================
            # Ingredients
            # =====================================

            recipe.recipe_ingredients.all().delete()


            for index, ingredient_data in enumerate(
                recipe_data.get(
                    "ingredients",
                    [],
                ),
                start=1,
            ):

                ingredient_name = ingredient_data[
                    "name"
                ]


                ingredient_defaults = {
                    "category":
                        ingredient_data.get(
                            "category",
                            "other",
                        ),

                    "is_seasoning":
                        ingredient_data.get(
                            "is_seasoning",
                            False,
                        ),

                    "switzerland_availability":
                        ingredient_data.get(
                            "switzerland_availability",
                            5,
                        ),
                }


                ingredient, _ = (
                    Ingredient.objects.update_or_create(
                        name=ingredient_name,
                        defaults=ingredient_defaults,
                    )
                )


                RecipeIngredient.objects.create(
                    recipe=recipe,
                    ingredient=ingredient,

                    amount=ingredient_data.get(
                        "amount",
                        "",
                    ),

                    is_optional=ingredient_data.get(
                        "is_optional",
                        False,
                    ),

                    display_order=index,
                )


            # =====================================
            # Mood tags
            # =====================================

            recipe.mood_tags.clear()


            for mood_name in recipe_data.get(
                "mood_tags",
                [],
            ):

                mood, _ = (
                    MoodTag.objects.get_or_create(
                        name=mood_name,
                    )
                )

                recipe.mood_tags.add(mood)


            # =====================================
            # Nutrition tags
            # =====================================

            recipe.nutrition_tags.clear()


            for nutrition_name in recipe_data.get(
                "nutrition_tags",
                [],
            ):

                nutrition, _ = (
                    NutritionTag.objects.get_or_create(
                        name=nutrition_name,
                    )
                )

                recipe.nutrition_tags.add(
                    nutrition
                )


            self.stdout.write(
                f"✓ {recipe.appliance.name} / {recipe.name}"
            )


        self.stdout.write("")


        self.stdout.write(
            self.style.SUCCESS(
                "インポート完了 "
                f"新規: {created_count} / "
                f"更新: {updated_count}"
            )
        )