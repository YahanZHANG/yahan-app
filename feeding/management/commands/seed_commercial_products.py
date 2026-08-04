from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from feeding.models import Dish, DishCategory, DishIngredient, Food
from .commercial_product_data import COMMERCIAL_PRODUCTS


FOOD_REFERENCE_ALIASES = {
    "かぼちゃ": ["かぼちゃ", "にんじん"],
    "じゃがいも": ["じゃがいも", "さつまいも", "にんじん"],
    "菜種油": ["菜種油", "オリーブオイル", "油"],
    "牛肉": ["牛肉", "鶏肉", "豚肉"],
    "米": ["米", "おかゆ", "うどん", "オートミール"],
    "にんじん": ["にんじん", "かぼちゃ"],
    "トマト": ["トマト", "にんじん"],
    "ズッキーニ": ["ズッキーニ", "きゅうり", "にんじん"],
    "クスクス": ["クスクス", "パスタ", "うどん", "米"],
    "ひよこ豆": ["ひよこ豆", "豆腐", "大豆"],
    "玉ねぎ": ["玉ねぎ", "長ねぎ", "にんじん"],
    "レンズ豆": ["レンズ豆", "豆腐", "大豆"],
    "ハム": ["ハム", "豚肉", "牛肉", "鶏肉"],
    "パスタ": ["パスタ", "うどん", "そうめん", "米"],
    "洋なし": ["洋なし", "りんご", "バナナ"],
    "プルーン": ["プルーン", "すもも", "りんご"],
    "全粒穀物": ["全粒穀物", "オートミール", "米"],
    "鶏肉": ["鶏肉", "牛肉"],
    "ビーツ": ["ビーツ", "にんじん"],
    "りんご": ["りんご", "バナナ"],
    "バナナ": ["バナナ", "りんご"],
    "オートミール": ["オートミール", "米"],
    "全粒小麦": ["全粒小麦", "小麦", "うどん", "パスタ"],
    "パースニップ": ["パースニップ", "にんじん"],
    "長ねぎ": ["長ねぎ", "玉ねぎ", "にんじん"],
    "ほうれん草": ["ほうれん草", "小松菜", "にんじん"],
    "グリーンピース": ["グリーンピース", "豆腐", "大豆"],
    "仔牛肉": ["仔牛肉", "牛肉", "鶏肉"],
    "全粒スペルトパスタ": ["全粒スペルトパスタ", "パスタ", "うどん"],
    "桃": ["桃", "りんご"],
    "あんず": ["あんず", "桃", "りんご"],
    "スペルト小麦": ["スペルト小麦", "小麦", "パスタ"],
    "ブルーベリー": ["ブルーベリー", "いちご", "りんご"],
    "ラズベリー": ["ラズベリー", "いちご", "りんご"],
    "いちご": ["いちご", "りんご"],
}


class Command(BaseCommand):
    help = "HiPP・Holleの市販離乳食を一括登録・更新する。"

    def add_arguments(self, parser):
        parser.add_argument("--brand", choices=["hipp", "holle"])
        parser.add_argument("--dry-run", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        brand_filter = options.get("brand")
        dry_run = options.get("dry_run", False)
        products = [
            p for p in COMMERCIAL_PRODUCTS
            if not brand_filter or p["brand"] == brand_filter
        ]

        category, _ = DishCategory.objects.get_or_create(
            name="市販品",
            defaults={"display_order": 999, "is_active": True},
        )

        created_count = updated_count = 0

        for p in products:
            name = (
                f'{p["display_month"]}か月｜'
                f'{p["german_name"]}｜'
                f'{p["japanese_name"]}'
            )

            if dry_run:
                self.stdout.write(f'[DRY RUN] {p["brand"]}: {name}')
                continue

            verified = p["ratio_source"] == "official"
            product, created = Dish.objects.update_or_create(
                name=name,
                defaults={
                    "category": category,
                    "finished_amount_g": Decimal(p["finished_amount_g"]),
                    "instructions": "",
                    "is_user_created": False,
                    "is_active": True,
                    "is_commercial_product": True,
                    "commercial_brand": p["brand"],
                    "recommended_from_month": p["recommended_from_month"],
                    "source_url": p["source_url"],
                    "ingredient_data_verified": verified,
                    "ingredient_data_note": self._build_note(p),
                },
            )

            created_count += int(created)
            updated_count += int(not created)
            retained_ids = []

            for food_name, percentage, source in p["ingredients"]:
                food = self._resolve_or_create_food(food_name)
                amount_g = (
                    Decimal(p["finished_amount_g"])
                    * Decimal(percentage)
                    / Decimal("100")
                ).quantize(Decimal("0.01"))

                DishIngredient.objects.update_or_create(
                    dish=product,
                    food=food,
                    defaults={"amount_g": amount_g},
                )
                retained_ids.append(food.pk)

            (
                DishIngredient.objects
                .filter(dish=product)
                .exclude(food_id__in=retained_ids)
                .delete()
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f'{"作成" if created else "更新"}: {name}'
                )
            )

        if dry_run:
            transaction.set_rollback(True)
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN完了：{len(products)}件。DB変更なし。"
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"完了：新規{created_count}件、更新{updated_count}件"
            )
        )

    def _build_note(self, p):
        source = p["ratio_source"]
        if source == "official":
            prefix = "公式商品ページに記載された材料割合を使用。"
        elif source == "official_partial":
            prefix = "公式割合とAI推定を併用。"
        else:
            prefix = "AI推定。商品名、原材料順、一般的な配合を基に換算。"

        details = ", ".join(
            f"{name} {pct}%"
            + ("（公式）" if src == "official" else "（推定）")
            for name, pct, src in p["ingredients"]
        )
        return f"{prefix} {details}"

    def _resolve_or_create_food(self, food_name):
        food = (
            Food.objects
            .filter(name__iexact=food_name)
            .select_related("category", "feeding_group")
            .first()
        )
        if food:
            return food

        aliases = FOOD_REFERENCE_ALIASES.get(food_name, [])
        reference = self._find_reference_food(aliases)

        if reference is None:
            raise CommandError(
                f"食材「{food_name}」の参照元が見つからない。"
                f"候補: {', '.join(aliases) or '未定義'}"
            )

        food = Food.objects.create(
            name=food_name,
            category=reference.category,
            feeding_group=reference.feeding_group,
            is_active=True,
            show_in_first_year_list=True,
        )
        self.stdout.write(
            self.style.WARNING(
                f"  食材を自動作成: {food_name}"
                f"（{reference.name}の分類を継承）"
            )
        )
        return food

    def _find_reference_food(self, aliases):
        if not aliases:
            return None
        query = Q()
        for alias in aliases:
            query |= Q(name__iexact=alias)
        return (
            Food.objects
            .filter(query)
            .select_related("category", "feeding_group")
            .order_by("id")
            .first()
        )
