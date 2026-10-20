"""
washoku/data/ingredients.json と recipes.json を取り込む。

    python manage.py import_washoku
    python manage.py import_washoku --dry-run

同じ名前の食材・レシピは上書きする。ただしレシピの公開状態は、
既にあるレシピでは変えない (管理画面で公開したものを下書きに戻さないため)。
レシピの材料が食材リストにない場合は、何も取り込まずにエラーにする。
"""

import json

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from washoku.models import (
    Ingredient,
    MoodTag,
    Recipe,
    RecipeIngredient,
    ShopType,
    Substitute,
)


DATA_DIR = Path(__file__).resolve().parents[2] / "data"


class DryRun(Exception):
    pass


class Command(BaseCommand):

    help = "スイスで和食の食材とレシピを JSON から取り込む"

    def add_arguments(self, parser):

        parser.add_argument(
            "--ingredients",
            default=str(DATA_DIR / "ingredients.json"),
        )

        parser.add_argument(
            "--recipes",
            default=str(DATA_DIR / "recipes.json"),
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="チェックだけして保存しない",
        )

    def handle(self, *args, **options):

        ingredients = self.load(options["ingredients"])
        recipes = self.load(options["recipes"])

        try:
            with transaction.atomic():

                ingredient_count = self.import_ingredients(ingredients)
                recipe_count = self.import_recipes(recipes)

                if options["dry_run"]:
                    raise DryRun

        except DryRun:
            self.stdout.write("チェックのみ (保存していません)")

        self.stdout.write(
            self.style.SUCCESS(
                f"食材 {ingredient_count}件、レシピ {recipe_count}件"
            )
        )

    def load(self, path):

        try:
            with open(path, encoding="utf-8") as file:
                return json.load(file)
        except FileNotFoundError:
            raise CommandError(f"ファイルがありません: {path}")
        except json.JSONDecodeError as error:
            raise CommandError(f"JSON が読めません: {path}: {error}")

    # -----------------------------------------------------
    # 食材
    # -----------------------------------------------------

    def import_ingredients(self, rows):

        shops = {shop.code: shop for shop in ShopType.objects.all()}

        for row in rows:

            unknown = [code for code in row.get("shops", []) if code not in shops]

            if unknown:
                raise CommandError(
                    f"{row['name']}: 店の種類が不明です: {', '.join(unknown)}"
                )

            ingredient, _ = Ingredient.objects.update_or_create(
                name=row["name"],
                defaults={
                    "name_de": row.get("name_de", ""),
                    "name_fr": row.get("name_fr", ""),
                    "category": row.get("category", "other"),
                    "search_group": row.get("search_group", ""),
                    "buying_notes": row.get("buying_notes", ""),
                },
            )

            ingredient.shops.set(
                [shops[code] for code in row.get("shops", [])]
            )

            for substitute in row.get("substitutes_for", []):

                Substitute.objects.update_or_create(
                    original_name=substitute["original_name"],
                    substitute=ingredient,
                    defaults={
                        "tips": substitute.get("tips", ""),
                    },
                )

        return len(rows)

    # -----------------------------------------------------
    # レシピ
    # -----------------------------------------------------

    def import_recipes(self, rows):

        self.check_references(rows)

        ingredients = {item.name: item for item in Ingredient.objects.all()}
        moods = {mood.name: mood for mood in MoodTag.objects.all()}

        for row in rows:

            steps = row["steps"]

            if isinstance(steps, list):
                steps = "\n".join(steps)

            defaults = {
                "description": row.get("description", ""),
                "category": row.get("category", "other"),
                "cooking_time_minutes": row.get("cooking_time_minutes"),
                "servings": row.get("servings"),
                "steps": steps,
                "swiss_tips": row.get("swiss_tips", ""),
                "origin": row.get("origin", "manual"),
                "is_tested": row.get("is_tested", False),
            }

            recipe, created = Recipe.objects.update_or_create(
                name=row["name"],
                defaults=defaults,
                create_defaults={
                    **defaults,
                    "status": row.get("status", "draft"),
                },
            )

            recipe.recipe_ingredients.all().delete()

            for order, item in enumerate(row.get("ingredients", []), start=1):

                RecipeIngredient.objects.create(
                    recipe=recipe,
                    ingredient=ingredients[item["name"]],
                    amount=item.get("amount", ""),
                    is_seasoning=item.get("is_seasoning", False),
                    is_optional=item.get("is_optional", False),
                    display_order=order,
                )

            recipe.mood_tags.set(
                [moods[name] for name in row.get("mood_tags", [])]
            )

            recipe.update_shop_rank()

        return len(rows)

    def check_references(self, rows):
        """
        食材リストや気分タグにない名前を、まとめて報告する。
        """

        ingredient_names = set(
            Ingredient.objects.values_list("name", flat=True)
        )

        mood_names = set(
            MoodTag.objects.values_list("name", flat=True)
        )

        problems = []

        for row in rows:

            for item in row.get("ingredients", []):
                if item["name"] not in ingredient_names:
                    problems.append(
                        f"{row['name']}: 食材リストにない材料「{item['name']}」"
                    )

            for name in row.get("mood_tags", []):
                if name not in mood_names:
                    problems.append(
                        f"{row['name']}: 気分タグにない「{name}」"
                    )

        if problems:
            raise CommandError(
                "取り込みを中止しました。\n" + "\n".join(problems)
            )
