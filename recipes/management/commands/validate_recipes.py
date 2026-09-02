import json
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import (
    BaseCommand,
    CommandError,
)
from django.core.validators import URLValidator

from recipes.constants import (
    MOOD_TAGS,
    NUTRITION_TAGS,
)
from recipes.models import (
    Appliance,
    Ingredient,
    Recipe,
)


class Command(BaseCommand):
    help = (
        "recipes/data/recipes.json を検証し、"
        "問題のあるレシピを表示する"
    )

    def handle(self, *args, **options):

        file_path = (
            Path(__file__)
            .resolve()
            .parents[2]
            / "data"
            / "recipes.json"
        )

        if not file_path.exists():
            raise CommandError(
                f"ファイルが見つからない: {file_path}"
            )

        try:
            with file_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                recipes_data = json.load(file)

        except json.JSONDecodeError as error:
            raise CommandError(
                "recipes.json のJSON形式が壊れている。\n"
                f"{error}"
            )


        if not isinstance(recipes_data, list):
            raise CommandError(
                "recipes.json の一番外側は "
                "[] のリスト形式にする必要がある。"
            )


        valid_appliance_types = {
            choice[0]
            for choice
            in Appliance.APPLIANCE_TYPES
        }

        valid_recipe_categories = {
            choice[0]
            for choice
            in Recipe.CATEGORY_CHOICES
        }

        valid_cooking_modes = {
            choice[0]
            for choice
            in Recipe.COOKING_MODE_CHOICES
        }

        valid_ingredient_categories = {
            choice[0]
            for choice
            in Ingredient.CATEGORY_CHOICES
        }


        url_validator = URLValidator(
            schemes=[
                "http",
                "https",
            ]
        )


        errors = []
        warnings = []

        seen_recipes = set()


        for index, recipe_data in enumerate(
            recipes_data,
            start=1,
        ):

            prefix = f"[{index}]"


            # =====================================
            # Recipe object
            # =====================================

            if not isinstance(
                recipe_data,
                dict,
            ):
                errors.append(
                    f"{prefix} レシピがobject形式ではない"
                )
                continue


            name = str(
                recipe_data.get(
                    "name",
                    "",
                )
            ).strip()

            appliance_type = str(
                recipe_data.get(
                    "appliance_type",
                    "",
                )
            ).strip()


            recipe_label = (
                f"{appliance_type or '?'} / "
                f"{name or '料理名なし'}"
            )


            # =====================================
            # Name
            # =====================================

            if not name:
                errors.append(
                    f"{prefix} 料理名がない"
                )


            # =====================================
            # Appliance
            # =====================================

            if appliance_type not in (
                valid_appliance_types
            ):
                errors.append(
                    f"{prefix} {recipe_label}: "
                    "appliance_type が不正 "
                    f"({appliance_type})"
                )

            elif not Appliance.objects.filter(
                appliance_type=appliance_type
            ).exists():

                errors.append(
                    f"{prefix} {recipe_label}: "
                    "この調理家電がDBに登録されていない"
                )


            # =====================================
            # Duplicate recipe
            #
            # 同じ家電内で同じ料理は禁止
            # 家電が違えば同じ料理名でもOK
            # =====================================

            duplicate_key = (
                appliance_type,
                name,
            )

            if (
                appliance_type
                and name
                and duplicate_key in seen_recipes
            ):

                errors.append(
                    f"{prefix} {recipe_label}: "
                    "同じ調理家電内で料理名が重複している"
                )

            else:
                seen_recipes.add(
                    duplicate_key
                )


            # =====================================
            # Category
            # =====================================

            category = recipe_data.get(
                "category",
                "",
            )

            if category not in (
                valid_recipe_categories
            ):
                errors.append(
                    f"{prefix} {recipe_label}: "
                    f"category が不正 ({category})"
                )

            elif category == "other":
                warnings.append(
                    f"{prefix} {recipe_label}: "
                    "カテゴリーが「その他」"
                )


            # =====================================
            # Cooking mode
            # =====================================

            cooking_mode = recipe_data.get(
                "cooking_mode",
                "",
            )

            if cooking_mode not in (
                valid_cooking_modes
            ):
                errors.append(
                    f"{prefix} {recipe_label}: "
                    "cooking_mode が不正 "
                    f"({cooking_mode})"
                )


            # =====================================
            # Cooking time
            # =====================================

            cooking_time = recipe_data.get(
                "cooking_time_minutes"
            )

            if cooking_time is not None:

                if (
                    not isinstance(
                        cooking_time,
                        int,
                    )
                    or cooking_time <= 0
                ):
                    errors.append(
                        f"{prefix} {recipe_label}: "
                        "cooking_time_minutes は"
                        "1以上の整数にする"
                    )


            # =====================================
            # Servings
            # =====================================

            servings = recipe_data.get(
                "servings"
            )

            if servings is not None:

                if (
                    not isinstance(
                        servings,
                        int,
                    )
                    or servings <= 0
                ):
                    errors.append(
                        f"{prefix} {recipe_label}: "
                        "servings は1以上の整数にする"
                    )


            # =====================================
            # Appliance operation
            # =====================================

            operation = str(
                recipe_data.get(
                    "appliance_operation",
                    "",
                )
            ).strip()

            if not operation:
                errors.append(
                    f"{prefix} {recipe_label}: "
                    "調理家電の操作方法がない"
                )


            # =====================================
            # Auto menu number
            # =====================================

            menu_number = str(
                recipe_data.get(
                    "menu_number",
                    "",
                )
            ).strip()

            if (
                cooking_mode == "auto"
                and not menu_number
            ):
                warnings.append(
                    f"{prefix} {recipe_label}: "
                    "自動調理だがmenu_numberが空"
                )


            # =====================================
            # Verification
            # =====================================

            if (
                recipe_data.get(
                    "verified_for_model"
                )
                is not True
            ):
                errors.append(
                    f"{prefix} {recipe_label}: "
                    "verified_for_model がTrueではない"
                )

            # =====================================
            # Make ahead
            # =====================================

            is_make_ahead = recipe_data.get(
                "is_make_ahead",
                False,
            )

            if not isinstance(
                is_make_ahead,
                bool,
            ):
                errors.append(
                    f"{prefix} {recipe_label}: "
                    "is_make_ahead は "
                    "true / false にする"
                )


            # =====================================
            # Source
            # =====================================

            source_name = str(
                recipe_data.get(
                    "source_name",
                    "",
                )
            ).strip()

            if not source_name:
                errors.append(
                    f"{prefix} {recipe_label}: "
                    "source_name がない"
                )


            source_url = str(
                recipe_data.get(
                    "source_url",
                    "",
                )
            ).strip()

            if not source_url:

                errors.append(
                    f"{prefix} {recipe_label}: "
                    "source_url がない"
                )

            else:

                try:
                    url_validator(
                        source_url
                    )

                except ValidationError:

                    errors.append(
                        f"{prefix} {recipe_label}: "
                        "source_url が正しいURLではない "
                        f"({source_url})"
                    )


            # =====================================
            # Switzerland score
            # =====================================

            swiss_score = recipe_data.get(
                "switzerland_score"
            )

            if (
                not isinstance(
                    swiss_score,
                    int,
                )
                or swiss_score not in range(1, 6)
            ):
                errors.append(
                    f"{prefix} {recipe_label}: "
                    "switzerland_score は1〜5"
                )


            # =====================================
            # Ingredients
            # =====================================

            ingredients = recipe_data.get(
                "ingredients",
                [],
            )

            if (
                not isinstance(
                    ingredients,
                    list,
                )
                or not ingredients
            ):

                errors.append(
                    f"{prefix} {recipe_label}: "
                    "材料が登録されていない"
                )

                continue


            seen_ingredients = set()


            for ingredient_index, ingredient in enumerate(
                ingredients,
                start=1,
            ):

                ingredient_prefix = (
                    f"{prefix} "
                    f"{recipe_label} "
                    f"材料{ingredient_index}"
                )


                if not isinstance(
                    ingredient,
                    dict,
                ):
                    errors.append(
                        f"{ingredient_prefix}: "
                        "object形式ではない"
                    )
                    continue


                ingredient_name = str(
                    ingredient.get(
                        "name",
                        "",
                    )
                ).strip()


                if not ingredient_name:

                    errors.append(
                        f"{ingredient_prefix}: "
                        "食材名がない"
                    )

                    continue


                # -----------------------------
                # Duplicate ingredient
                # -----------------------------

                if ingredient_name in (
                    seen_ingredients
                ):

                    errors.append(
                        f"{ingredient_prefix}: "
                        f"{ingredient_name} が重複している"
                    )

                else:
                    seen_ingredients.add(
                        ingredient_name
                    )


                # -----------------------------
                # Ingredient category
                # -----------------------------

                ingredient_category = (
                    ingredient.get(
                        "category",
                        "",
                    )
                )

                if ingredient_category not in (
                    valid_ingredient_categories
                ):

                    errors.append(
                        f"{ingredient_prefix}: "
                        "category が不正 "
                        f"({ingredient_category})"
                    )


                # -----------------------------
                # is_seasoning
                # -----------------------------

                if "is_seasoning" not in (
                    ingredient
                ):

                    errors.append(
                        f"{ingredient_prefix}: "
                        "is_seasoning がない"
                    )

                elif not isinstance(
                    ingredient[
                        "is_seasoning"
                    ],
                    bool,
                ):

                    errors.append(
                        f"{ingredient_prefix}: "
                        "is_seasoning は "
                        "true / false にする"
                    )


                # -----------------------------
                # Amount
                # -----------------------------

                amount = str(
                    ingredient.get(
                        "amount",
                        "",
                    )
                ).strip()

                if not amount:

                    warnings.append(
                        f"{ingredient_prefix}: "
                        f"{ingredient_name} の分量がない"
                    )


                # -----------------------------
                # Search group
                # -----------------------------

                is_seasoning = (
                    ingredient.get(
                        "is_seasoning"
                    )
                    is True
                )

                search_group = str(
                    ingredient.get(
                        "search_group",
                        "",
                    )
                ).strip()


                if (
                    not is_seasoning
                    and not search_group
                ):
                    warnings.append(
                        f"{ingredient_prefix}: "
                        f"{ingredient_name} に"
                        "search_groupがない "
                        "（食材名と同じ扱いになる）"
                    )


                # -----------------------------
                # Switzerland availability
                # -----------------------------

                availability = ingredient.get(
                    "switzerland_availability"
                )

                if availability is not None:

                    if (
                        not isinstance(
                            availability,
                            int,
                        )
                        or availability
                        not in range(1, 6)
                    ):
                        errors.append(
                            f"{ingredient_prefix}: "
                            "switzerland_availability "
                            "は1〜5"
                        )


            # =====================================
            # Mood tags
            # =====================================

            mood_tags = recipe_data.get(
                "mood_tags",
                [],
            )

            if not isinstance(
                mood_tags,
                list,
            ):
                errors.append(
                    f"{prefix} {recipe_label}: "
                    "mood_tags はリスト形式にする"
                )

            else:

                for mood in mood_tags:

                    if mood not in MOOD_TAGS:

                        errors.append(
                            f"{prefix} {recipe_label}: "
                            "未定義の気分タグ "
                            f"「{mood}」"
                        )


            # =====================================
            # Nutrition tags
            # =====================================

            nutrition_tags = recipe_data.get(
                "nutrition_tags",
                [],
            )

            if not isinstance(
                nutrition_tags,
                list,
            ):
                errors.append(
                    f"{prefix} {recipe_label}: "
                    "nutrition_tags はリスト形式にする"
                )

            else:

                for nutrition in nutrition_tags:

                    if nutrition not in (
                        NUTRITION_TAGS
                    ):
                        errors.append(
                            f"{prefix} {recipe_label}: "
                            "未定義の栄養タグ "
                            f"「{nutrition}」"
                        )


        # =====================================
        # Result
        # =====================================

        self.stdout.write("")
        self.stdout.write(
            "=" * 60
        )

        self.stdout.write(
            f"レシピ数: {len(recipes_data)}"
        )

        self.stdout.write(
            f"ERROR: {len(errors)}"
        )

        self.stdout.write(
            f"WARNING: {len(warnings)}"
        )

        self.stdout.write(
            "=" * 60
        )


        if warnings:

            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "WARNINGS"
                )
            )

            for warning in warnings:
                self.stdout.write(
                    self.style.WARNING(
                        f"⚠ {warning}"
                    )
                )


        if errors:

            self.stdout.write("")
            self.stdout.write(
                self.style.ERROR(
                    "ERRORS"
                )
            )

            for error in errors:
                self.stdout.write(
                    self.style.ERROR(
                        f"✗ {error}"
                    )
                )


            self.stdout.write("")

            raise CommandError(
                "レシピ検証に失敗した。"
                "上のERRORを修正してから"
                "import_recipesを実行すること。"
            )


        self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS(
                "✓ レシピ検証OK"
            )
        )