"""
washoku/data/ingredients.json・recipes.json・stores.json・links.json を取り込む。

    python manage.py import_washoku
    python manage.py import_washoku --dry-run
    python manage.py import_washoku --new-only   # まだない食材・レシピだけ追加 (start.sh 用)
                                                 # 既にあるものには、空の栄養の目安と新しい代用品だけ足す
    python manage.py import_washoku --no-geocode # お店の位置を調べない (ネットがないとき)

同じ名前の食材・レシピ・お店は上書きする。ただしレシピの公開状態は、
既にあるレシピでは変えない (管理画面で公開したものを下書きに戻さないため)。
レシピの材料が食材リストにない場合は、何も取り込まずにエラーにする。
参考リンクは、同じ URL がまだないものだけ追加する (管理画面で直したものは変えない)。
最後に、位置 (緯度・経度) がまだないお店を住所から調べる。
"""

import json

from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from washoku.geocode import geocode_missing_stores
from washoku.models import (
    Ingredient,
    MoodTag,
    Post,
    Recipe,
    RecipeIngredient,
    ShopType,
    Store,
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
            "--stores",
            default=str(DATA_DIR / "stores.json"),
        )

        parser.add_argument(
            "--links",
            default=str(DATA_DIR / "links.json"),
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="チェックだけして保存しない",
        )

        parser.add_argument(
            "--new-only",
            action="store_true",
            help="まだない食材・レシピだけ追加し、既にあるもの (管理画面で直したもの) は変えない",
        )

        parser.add_argument(
            "--no-geocode",
            action="store_true",
            help="お店の位置 (緯度・経度) を調べない",
        )

    def handle(self, *args, **options):

        ingredients = self.load(options["ingredients"])
        recipes = self.load(options["recipes"])
        stores = self.load(options["stores"])
        links = self.load(options["links"])

        all_ingredients = ingredients
        all_recipes = recipes

        if options["new_only"]:

            existing_ingredients = set(
                Ingredient.objects.values_list("name", flat=True)
            )
            existing_recipes = set(
                Recipe.objects.values_list("name", flat=True)
            )

            ingredients = [
                row for row in ingredients
                if row["name"] not in existing_ingredients
            ]
            recipes = [
                row for row in recipes
                if row["name"] not in existing_recipes
            ]

            existing_stores = set(
                Store.objects.values_list("name", flat=True)
            )
            stores = [
                row for row in stores
                if row["name"] not in existing_stores
            ]

        try:
            with transaction.atomic():

                ingredient_count = self.import_ingredients(ingredients)
                recipe_count = self.import_recipes(recipes)
                store_count = self.import_stores(stores)
                link_count = self.import_links(links)

                if link_count:
                    self.stdout.write(f"参考リンク {link_count}件を追加")

                if options["new_only"]:
                    substitute_count = self.add_missing_substitutes(all_ingredients)
                    nutrition_count = self.fill_missing_nutrition(all_recipes)

                    if substitute_count or nutrition_count:
                        self.stdout.write(
                            f"代用品 {substitute_count}件、栄養の目安 {nutrition_count}件を追加"
                        )

                if options["dry_run"]:
                    raise DryRun

        except DryRun:
            self.stdout.write("チェックのみ (保存していません)")

        self.stdout.write(
            self.style.SUCCESS(
                f"食材 {ingredient_count}件、レシピ {recipe_count}件、お店 {store_count}件"
            )
        )

        if not options["dry_run"] and not options["no_geocode"]:

            missing = Store.objects.filter(latitude__isnull=True).count()

            if missing:
                found = geocode_missing_stores()
                self.stdout.write(f"お店の位置: {missing}件中 {found}件を住所から調べました")

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

    def add_missing_substitutes(self, rows):
        """
        既にある食材に、JSON で新しく足した代用品を追加する (既にあるものは変えない)。
        """

        ingredients = {item.name: item for item in Ingredient.objects.all()}

        count = 0

        for row in rows:

            ingredient = ingredients.get(row["name"])

            if ingredient is None:
                continue

            for substitute in row.get("substitutes_for", []):

                _, created = Substitute.objects.get_or_create(
                    original_name=substitute["original_name"],
                    substitute=ingredient,
                    defaults={
                        "tips": substitute.get("tips", ""),
                    },
                )

                count += created

        return count

    # -----------------------------------------------------
    # お店
    # -----------------------------------------------------

    def import_stores(self, rows):

        for row in rows:

            defaults = {
                key: value
                for key, value in row.items()
                if key != "name"
            }

            store = Store.objects.filter(name=row["name"]).first()

            # 住所が変わったら位置を調べ直す
            if store and store.address != row["address"]:
                defaults.update(latitude=None, longitude=None)

            Store.objects.update_or_create(
                name=row["name"],
                defaults=defaults,
            )

        return len(rows)

    # -----------------------------------------------------
    # 参考リンク
    # -----------------------------------------------------

    def import_links(self, rows):
        """
        同じ URL の参考リンクがまだなければ追加する。紹介者は最初の管理者にする。
        """

        author = (
            get_user_model().objects
            .filter(is_superuser=True)
            .order_by("pk")
            .first()
        )

        count = 0

        for row in rows:

            if Post.objects.filter(kind="link", url=row["url"]).exists():
                continue

            Post.objects.create(
                kind="link",
                title=row["title"],
                url=row["url"],
                source=row.get("source", ""),
                body=row["body"],
                status=row.get("status", "draft"),
                author=author,
            )

            count += 1

        return count

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
                **row.get("nutrition", {}),
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

    def fill_missing_nutrition(self, rows):
        """
        栄養の目安がまだないレシピにだけ、JSON の値を入れる。
        """

        count = 0

        for row in rows:

            nutrition = row.get("nutrition")

            if not nutrition:
                continue

            count += Recipe.objects.filter(
                name=row["name"],
                energy_kcal__isnull=True,
            ).update(**nutrition)

        return count

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
