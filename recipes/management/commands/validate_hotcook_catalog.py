import json
from collections import Counter
from pathlib import Path

from django.conf import settings
from django.core.management.base import (
    BaseCommand,
    CommandError,
)


EXPECTED_HOTCOOK_TOTAL = 145
EXPECTED_HOTCOOK_AUTO = 126
EXPECTED_HOTCOOK_MANUAL = 19

HOTCOOK_APPLIANCE_TYPE = "hotcook"


class Command(BaseCommand):

    help = (
        "KN-HW16E公式メニュー集が "
        "145件（自動126 / 手動19）"
        "そろっているか確認します。"
    )


    def add_arguments(self, parser):

        parser.add_argument(
            "--path",
            default=None,
            help=(
                "検証するJSONファイル。"
                "省略時は recipes/data/recipes.json"
            ),
        )


    def handle(self, *args, **options):

        json_path = options["path"]

        if json_path:
            path = Path(json_path)

        else:
            path = (
                Path(settings.BASE_DIR)
                / "recipes"
                / "data"
                / "recipes.json"
            )


        if not path.exists():

            raise CommandError(
                f"JSONファイルが見つかりません: {path}"
            )


        try:

            with path.open(
                "r",
                encoding="utf-8",
            ) as file:

                data = json.load(file)

        except json.JSONDecodeError as error:

            raise CommandError(
                f"JSON形式が不正です: {error}"
            )


        if not isinstance(data, list):

            raise CommandError(
                "JSONの最上位は配列である必要があります。"
            )


        hotcook_recipes = [
            recipe
            for recipe in data
            if recipe.get("appliance_type")
            == HOTCOOK_APPLIANCE_TYPE
        ]


        auto_recipes = [
            recipe
            for recipe in hotcook_recipes
            if recipe.get("cooking_mode")
            == "auto"
        ]


        manual_recipes = [
            recipe
            for recipe in hotcook_recipes
            if recipe.get("cooking_mode")
            == "manual"
        ]


        errors = []
        warnings = []


        # =================================================
        # 件数
        # =================================================

        if (
            len(hotcook_recipes)
            != EXPECTED_HOTCOOK_TOTAL
        ):

            errors.append(
                "Hotcook件数が一致しません。"
                f" expected="
                f"{EXPECTED_HOTCOOK_TOTAL},"
                f" actual="
                f"{len(hotcook_recipes)}"
            )


        if (
            len(auto_recipes)
            != EXPECTED_HOTCOOK_AUTO
        ):

            errors.append(
                "自動メニュー件数が一致しません。"
                f" expected="
                f"{EXPECTED_HOTCOOK_AUTO},"
                f" actual="
                f"{len(auto_recipes)}"
            )


        if (
            len(manual_recipes)
            != EXPECTED_HOTCOOK_MANUAL
        ):

            errors.append(
                "手動メニュー件数が一致しません。"
                f" expected="
                f"{EXPECTED_HOTCOOK_MANUAL},"
                f" actual="
                f"{len(manual_recipes)}"
            )


        # =================================================
        # 料理名の重複
        # =================================================

        names = [
            recipe.get(
                "name",
                "",
            ).strip()
            for recipe in hotcook_recipes
        ]


        duplicate_names = sorted(
            name
            for name, count
            in Counter(names).items()
            if name and count > 1
        )


        for name in duplicate_names:

            errors.append(
                f"料理名が重複しています: {name}"
            )


        # =================================================
        # 自動メニュー番号
        # =================================================

        auto_menu_numbers = []


        for recipe in auto_recipes:

            name = recipe.get(
                "name",
                "(名前なし)",
            )

            menu_number = str(
                recipe.get(
                    "menu_number",
                    "",
                )
            ).strip()


            if not menu_number:

                errors.append(
                    "自動メニューなのに"
                    "menu_numberがありません: "
                    f"{name}"
                )

                continue


            auto_menu_numbers.append(
                menu_number
            )


        duplicate_menu_numbers = sorted(
            menu_number
            for menu_number, count
            in Counter(
                auto_menu_numbers
            ).items()
            if count > 1
        )


        for menu_number in (
            duplicate_menu_numbers
        ):

            errors.append(
                "自動メニュー番号が"
                "重複しています: "
                f"{menu_number}"
            )


        # =================================================
        # verified_for_model
        # =================================================

        for recipe in hotcook_recipes:

            name = recipe.get(
                "name",
                "(名前なし)",
            )

            if (
                recipe.get(
                    "verified_for_model"
                )
                is not True
            ):

                errors.append(
                    "verified_for_model が"
                    "trueではありません: "
                    f"{name}"
                )


        # =================================================
        # 出典
        # =================================================

        for recipe in hotcook_recipes:

            name = recipe.get(
                "name",
                "(名前なし)",
            )

            source_name = str(
                recipe.get(
                    "source_name",
                    "",
                )
            ).strip()

            source_url = str(
                recipe.get(
                    "source_url",
                    "",
                )
            ).strip()


            if not source_name:

                errors.append(
                    "source_name が"
                    "ありません: "
                    f"{name}"
                )


            if not source_url:

                errors.append(
                    "source_url が"
                    "ありません: "
                    f"{name}"
                )


        # =================================================
        # preparation
        # =================================================

        for recipe in hotcook_recipes:

            name = recipe.get(
                "name",
                "(名前なし)",
            )

            preparation = str(
                recipe.get(
                    "preparation",
                    "",
                )
            ).strip()


            if not preparation:

                errors.append(
                    "作り方 preparation が"
                    "ありません: "
                    f"{name}"
                )


            elif len(preparation) < 30:

                warnings.append(
                    "作り方がかなり短いです: "
                    f"{name} "
                    f"({len(preparation)}文字)"
                )


        # =================================================
        # appliance_operation
        # =================================================

        for recipe in hotcook_recipes:

            name = recipe.get(
                "name",
                "(名前なし)",
            )

            operation = str(
                recipe.get(
                    "appliance_operation",
                    "",
                )
            ).strip()


            if not operation:

                errors.append(
                    "appliance_operation が"
                    "ありません: "
                    f"{name}"
                )


        # =================================================
        # 結果表示
        # =================================================

        self.stdout.write(
            ""
        )

        self.stdout.write(
            "========================================"
        )

        self.stdout.write(
            "KN-HW16E Catalog Validation"
        )

        self.stdout.write(
            "========================================"
        )

        self.stdout.write(
            f"JSON total: "
            f"{len(data)}"
        )

        self.stdout.write(
            f"Hotcook total: "
            f"{len(hotcook_recipes)} "
            f"/ {EXPECTED_HOTCOOK_TOTAL}"
        )

        self.stdout.write(
            f"Auto: "
            f"{len(auto_recipes)} "
            f"/ {EXPECTED_HOTCOOK_AUTO}"
        )

        self.stdout.write(
            f"Manual: "
            f"{len(manual_recipes)} "
            f"/ {EXPECTED_HOTCOOK_MANUAL}"
        )

        self.stdout.write(
            ""
        )


        if warnings:

            self.stdout.write(
                self.style.WARNING(
                    f"WARNING: "
                    f"{len(warnings)}"
                )
            )

            for warning in warnings:

                self.stdout.write(
                    f"  - {warning}"
                )

        else:

            self.stdout.write(
                self.style.SUCCESS(
                    "WARNING: 0"
                )
            )


        self.stdout.write(
            ""
        )


        if errors:

            self.stdout.write(
                self.style.ERROR(
                    f"ERROR: "
                    f"{len(errors)}"
                )
            )

            for error in errors:

                self.stdout.write(
                    f"  - {error}"
                )

            raise CommandError(
                "KN-HW16Eメニュー集の"
                "検証に失敗しました。"
            )


        self.stdout.write(
            self.style.SUCCESS(
                "ERROR: 0"
            )
        )

        self.stdout.write(
            ""
        )

        self.stdout.write(
            self.style.SUCCESS(
                "✓ KN-HW16E公式メニュー集"
                "145件の構成OK"
            )
        )