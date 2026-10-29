import json
import tempfile

from datetime import timedelta

from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Comment,
    DisplaySettings,
    Feedback,
    HouseholdInvite,
    Ingredient,
    MemberPhoto,
    MoodTag,
    Notification,
    CommentReaction,
    PollChoice,
    PollSuggestion,
    PollVote,
    Post,
    PostReaction,
    Recipe,
    RecipeFavorite,
    RecipeIngredient,
    RecipeNote,
    RecipeRating,
    ShopType,
    Store,
    Substitute,
)


INGREDIENTS = [
    {
        "name": "鶏もも肉",
        "name_de": "Pouletschenkel",
        "category": "meat",
        "search_group": "鶏肉",
        "shops": ["supermarket"],
    },
    {
        "name": "醤油",
        "category": "seasoning",
        "shops": ["supermarket", "asian"],
    },
    {
        "name": "みりん",
        "category": "seasoning",
        "shops": ["asian", "japanese"],
    },
    {
        "name": "Rettich",
        "category": "vegetable",
        "shops": ["supermarket"],
        "substitutes_for": [
            {"original_name": "大根", "tips": "少し辛いので下茹でを長めに。"},
        ],
    },
]

RECIPES = [
    {
        "name": "照り焼きチキン",
        "category": "meat",
        "steps": ["鶏肉を焼く", "タレを絡める"],
        "mood_tags": ["がっつり"],
        "origin": "ai",
        "ingredients": [
            {"name": "鶏もも肉", "amount": "2枚"},
            {"name": "醤油", "amount": "大さじ2", "is_seasoning": True},
            {"name": "みりん", "amount": "大さじ2", "is_seasoning": True, "is_optional": True},
        ],
    },
]


class ImportTests(TestCase):

    def run_import(self, ingredients=INGREDIENTS, recipes=RECIPES, **options):

        with tempfile.TemporaryDirectory() as directory:

            ingredients_path = Path(directory) / "ingredients.json"
            recipes_path = Path(directory) / "recipes.json"

            ingredients_path.write_text(json.dumps(ingredients), encoding="utf-8")
            recipes_path.write_text(json.dumps(recipes), encoding="utf-8")

            call_command(
                "import_washoku",
                ingredients=str(ingredients_path),
                recipes=str(recipes_path),
                stdout=open("/dev/null", "w"),
                no_geocode=True,
                **options,
            )

    def test_seeded_shop_types_and_moods(self):
        self.assertEqual(
            list(ShopType.objects.values_list("code", flat=True)),
            ["supermarket", "asian", "japanese", "online"],
        )
        self.assertTrue(MoodTag.objects.filter(name="がっつり").exists())

    def test_approved_recipes_are_created_published(self):

        self.run_import(recipes=[{**RECIPES[0], "status": "published"}])

        self.assertEqual(Recipe.objects.get(name="照り焼きチキン").status, "published")

    def test_bundled_recipes_are_approved_except_new_drafts(self):

        from .data.build_data import DRAFT_RECIPES

        recipes = json.loads((Path(__file__).parent / "data" / "recipes.json").read_text(encoding="utf-8"))

        drafts = {recipe["name"] for recipe in recipes if recipe["status"] == "draft"}

        self.assertEqual(drafts, DRAFT_RECIPES)
        self.assertGreaterEqual(len([r for r in recipes if r["category"] == "yoshoku"]), 15)

    def test_bundled_recipes_all_have_nutrition(self):

        recipes = json.loads((Path(__file__).parent / "data" / "recipes.json").read_text(encoding="utf-8"))

        for recipe in recipes:
            with self.subTest(recipe=recipe["name"]):
                nutrition = recipe["nutrition"]
                self.assertGreater(nutrition["energy_kcal"], 0)
                # エネルギーと PFC の合計がだいたい合っているか (±25%)
                from_pfc = nutrition["protein_g"] * 4 + nutrition["fat_g"] * 9 + nutrition["carbs_g"] * 4
                self.assertLess(abs(from_pfc - nutrition["energy_kcal"]) / nutrition["energy_kcal"], 0.25)

    def test_new_only_fills_missing_nutrition_and_substitutes_without_overwriting(self):

        self.run_import()

        recipe = Recipe.objects.get(name="照り焼きチキン")
        self.assertIsNone(recipe.energy_kcal)

        nutrition = {"energy_kcal": 340, "protein_g": 28, "fat_g": 20, "carbs_g": 12, "salt_g": 2.6}
        ingredients = [
            *INGREDIENTS[:3],
            {
                **INGREDIENTS[3],
                "substitutes_for": [
                    {"original_name": "大根", "tips": "新しい説明"},
                    {"original_name": "かぶ", "tips": "薄く切る"},
                ],
            },
        ]

        self.run_import(ingredients=ingredients, recipes=[{**RECIPES[0], "nutrition": nutrition}], new_only=True)

        recipe.refresh_from_db()
        self.assertEqual(recipe.energy_kcal, 340)
        self.assertEqual(
            dict(Substitute.objects.values_list("original_name", "tips")),
            {"大根": "少し辛いので下茹でを長めに。", "かぶ": "薄く切る"},
        )

        # 管理画面で直した値は上書きしない
        Recipe.objects.filter(pk=recipe.pk).update(energy_kcal=300)
        self.run_import(recipes=[{**RECIPES[0], "nutrition": nutrition}], new_only=True)
        recipe.refresh_from_db()
        self.assertEqual(recipe.energy_kcal, 300)

    def test_new_only_fills_empty_buying_notes_only(self):

        self.run_import()
        Ingredient.objects.filter(name="醤油").update(buying_notes="管理画面で書いたメモ")

        ingredients = [
            {**row, "buying_notes": f"{row['name']}の新しいメモ"}
            for row in INGREDIENTS
        ]

        self.run_import(ingredients=ingredients, new_only=True)

        notes = dict(Ingredient.objects.values_list("name", "buying_notes"))
        self.assertEqual(notes["鶏もも肉"], "鶏もも肉の新しいメモ")
        self.assertEqual(notes["醤油"], "管理画面で書いたメモ")

    def test_bundled_recipes_have_sweets_bread_and_apero(self):

        recipes = json.loads((Path(__file__).parent / "data" / "recipes.json").read_text(encoding="utf-8"))
        categories = {recipe["name"]: recipe["category"] for recipe in recipes}

        self.assertEqual(categories["どら焼き"], "sweets")

        for category in ("sweets", "bread", "apero"):
            with self.subTest(category=category):
                self.assertGreaterEqual(list(categories.values()).count(category), 5)

    def test_import_creates_recipes_as_drafts(self):

        self.run_import()

        recipe = Recipe.objects.get(name="照り焼きチキン")

        self.assertEqual(recipe.status, "draft")
        self.assertEqual(recipe.origin, "ai")
        self.assertEqual(recipe.step_list(), ["鶏肉を焼く", "タレを絡める"])
        self.assertEqual(recipe.recipe_ingredients.count(), 3)
        self.assertEqual(list(recipe.mood_tags.values_list("name", flat=True)), ["がっつり"])
        self.assertEqual(
            Substitute.objects.get(original_name="大根").substitute.name,
            "Rettich",
        )

    def test_shop_rank_ignores_optional_ingredients(self):

        self.run_import()

        # みりんはアジアスーパーが必要だが「なくてもよい」なので普通のスーパーで作れる
        self.assertEqual(Recipe.objects.get(name="照り焼きチキン").shop_rank, 1)

    def test_shop_rank_uses_the_farthest_required_shop(self):

        recipes = json.loads(json.dumps(RECIPES))
        recipes[0]["ingredients"][2]["is_optional"] = False

        self.run_import(recipes=recipes)

        self.assertEqual(Recipe.objects.get(name="照り焼きチキン").shop_rank, 2)

    def test_reimport_keeps_published_status(self):

        self.run_import()
        Recipe.objects.update(status="published")

        self.run_import()

        self.assertEqual(Recipe.objects.get().status, "published")
        self.assertEqual(Recipe.objects.get().recipe_ingredients.count(), 3)

    def test_unknown_ingredient_stops_the_whole_import(self):

        recipes = json.loads(json.dumps(RECIPES))
        recipes[0]["ingredients"].append({"name": "みょうが"})

        with self.assertRaisesMessage(CommandError, "みょうが"):
            self.run_import(recipes=recipes)

        self.assertFalse(Ingredient.objects.exists())
        self.assertFalse(Recipe.objects.exists())

    def test_dry_run_saves_nothing(self):

        self.run_import(dry_run=True)

        self.assertFalse(Recipe.objects.exists())


class CommentTests(TestCase):

    def test_comment_needs_exactly_one_target(self):

        user = get_user_model().objects.create_user("taro", password="x")

        with self.assertRaises(IntegrityError):
            Comment.objects.create(author=user, body="どこで買える？")


def make_recipe(name="照り焼きチキン", status="published", **fields):

    shop = ShopType.objects.get(code="supermarket")

    chicken, _ = Ingredient.objects.get_or_create(name="鶏もも肉", defaults={"search_group": "鶏肉", "category": "meat"})
    chicken.shops.add(shop)

    soy, _ = Ingredient.objects.get_or_create(name="醤油", defaults={"category": "seasoning"})
    soy.shops.add(shop)

    recipe = Recipe.objects.create(name=name, steps="焼く\nタレを絡める", status=status, **fields)

    RecipeIngredient.objects.create(recipe=recipe, ingredient=chicken, amount="2枚")
    RecipeIngredient.objects.create(recipe=recipe, ingredient=soy, amount="大さじ2", is_seasoning=True)

    recipe.update_shop_rank()

    return recipe


class PageTests(TestCase):

    def setUp(self):
        self.recipe = make_recipe()
        self.draft = make_recipe("下書きの料理", status="draft")

    def test_pages_render(self):

        for url in [
            reverse("washoku:home"),
            reverse("washoku:recipe_list"),
            reverse("washoku:find_by_mood"),
            reverse("washoku:find_by_ingredients") + "?g=鶏肉",
            reverse("washoku:random_recipe"),
            reverse("washoku:recipe_detail", args=[self.recipe.pk]),
            reverse("washoku:ingredient_list"),
            reverse("washoku:ingredient_detail", args=[self.recipe.ingredients.first().pk]),
            reverse("washoku:question_list"),
            reverse("washoku:store_list"),
            reverse("washoku:store_list") + "?kind=japanese",
            reverse("washoku:about"),
            reverse("washoku:substitute_list"),
            reverse("washoku:column_list"),
            reverse("washoku:product_list") + "?shop=migros&section=frozen",
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_drafts_are_hidden_from_visitors_but_shown_to_staff(self):

        url = reverse("washoku:recipe_detail", args=[self.draft.pk])

        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertNotContains(self.client.get(reverse("washoku:recipe_list")), "下書きの料理")

        staff = get_user_model().objects.create_user("admin", password="x", is_staff=True)
        self.client.force_login(staff)

        self.assertContains(self.client.get(url), "下書き")

    def test_search_by_ingredient_group_and_shop(self):

        response = self.client.get(reverse("washoku:recipe_list") + "?q=鶏肉&shop=1")

        self.assertContains(response, "照り焼きチキン")

    def test_find_by_ingredients_must_use_filters_recipes(self):

        egg = Ingredient.objects.create(name="卵", category="egg")
        omelet = make_recipe("卵焼き")
        omelet.recipe_ingredients.filter(ingredient__name="鶏もも肉").delete()
        RecipeIngredient.objects.create(recipe=omelet, ingredient=egg, amount="2個")

        url = reverse("washoku:find_by_ingredients")

        both = self.client.get(url + "?g=鶏肉&g=卵")
        self.assertContains(both, "照り焼きチキン")
        self.assertContains(both, "卵焼き")

        must = self.client.get(url + "?g=鶏肉&g=卵&m=卵")
        self.assertNotContains(must, "照り焼きチキン</strong>")
        self.assertContains(must, "卵焼き")
        self.assertContains(must, "必ず使う: <strong>卵</strong>")

        # 「必ず使う」だけでも「ある」として扱う
        self.assertContains(self.client.get(url + "?m=卵"), "卵焼き")

    def test_find_by_ingredients_lists_missing_items(self):

        response = self.client.get(reverse("washoku:find_by_ingredients") + "?g=鶏肉")

        self.assertContains(response, "今ある食材で作れます")

    def test_home_uses_the_app_icon(self):
        self.assertContains(self.client.get(reverse("washoku:home")), "/static/pwa/washoku/")

    def test_portal_teases_the_app(self):
        self.assertContains(self.client.get(reverse("portal:home")), "スイスで和食")


class FamilyRatingTests(TestCase):

    def setUp(self):
        User = get_user_model()
        self.taro = User.objects.create_user("taro", password="x")
        self.hanako = User.objects.create_user("hanako", password="x")
        self.recipe = make_recipe()

    def test_invite_accept_and_see_each_others_ratings(self):

        self.client.force_login(self.taro)
        self.client.post(reverse("washoku:family_invite"), {"username": "hanako"})

        invite = HouseholdInvite.objects.get()

        self.client.force_login(self.hanako)
        self.client.post(reverse("washoku:family_respond", args=[invite.pk]), {"action": "accept"})
        self.client.post(reverse("washoku:rate_recipe", args=[self.recipe.pk]), {"rating": "5"})

        self.client.force_login(self.taro)
        response = self.client.get(reverse("washoku:recipe_detail", args=[self.recipe.pk]))

        self.assertContains(response, "hanako")
        self.assertContains(response, "★★★★★")

    def test_random_skips_dishes_someone_dislikes(self):

        RecipeRating.objects.create(user=self.taro, recipe=self.recipe, rating=1)

        self.client.force_login(self.taro)
        response = self.client.get(reverse("washoku:random_recipe"))

        self.assertIsNone(response.context["recipe"])


class CommentViewTests(TestCase):

    def setUp(self):
        User = get_user_model()
        self.taro = User.objects.create_user("taro", password="x")
        self.hanako = User.objects.create_user("hanako", password="x")
        self.recipe = make_recipe()
        self.url = reverse("washoku:comment_create", args=["recipe", self.recipe.pk])

    def post_comment(self, user, **data):
        self.client.force_login(user)
        return self.client.post(self.url, {"kind": "question", "body": "みりんはどこで買えますか？", **data})

    def test_question_reply_notifies_and_answers(self):

        self.post_comment(self.taro)
        question = Comment.objects.get()

        self.assertContains(self.client.get(reverse("washoku:question_list")), "みりん")

        self.post_comment(self.hanako, body="Coop のアジアコーナーにあります", parent=question.pk)

        reply = Comment.objects.get(parent=question)
        self.assertEqual(reply.kind, "tip")
        self.assertEqual(Notification.objects.get().recipient, self.taro)
        # 答えが出た質問は、下の「答えが出た質問」に移る
        html = self.client.get(reverse("washoku:question_list")).content.decode()
        self.assertLess(html.index("答えが出た質問"), html.index("みりん"))

    def test_reply_to_a_reply_stays_one_level(self):

        self.post_comment(self.taro)
        question = Comment.objects.get()

        self.post_comment(self.hanako, parent=question.pk)
        reply = Comment.objects.get(parent=question)

        Comment.objects.update(created_at=timezone.now() - timedelta(minutes=5))

        self.post_comment(self.taro, parent=reply.pk)

        self.assertEqual(question.replies.count(), 2)

    def test_posting_too_fast_is_refused(self):

        self.post_comment(self.taro)
        self.post_comment(self.taro)

        self.assertEqual(Comment.objects.count(), 1)

    def test_only_author_can_edit_and_delete(self):

        self.post_comment(self.taro)
        comment = Comment.objects.get()

        self.client.force_login(self.hanako)
        self.assertEqual(self.client.get(reverse("washoku:comment_edit", args=[comment.pk])).status_code, 404)

        self.client.force_login(self.taro)
        self.client.post(reverse("washoku:comment_edit", args=[comment.pk]), {"body": "直しました"})

        comment.refresh_from_db()
        self.assertEqual(comment.body, "直しました")
        self.assertIsNotNone(comment.edited_at)

        self.client.post(reverse("washoku:comment_delete", args=[comment.pk]))
        self.assertFalse(Comment.objects.exists())

    def test_deleting_a_comment_with_replies_keeps_the_thread(self):

        self.post_comment(self.taro)
        question = Comment.objects.get()
        self.post_comment(self.hanako, parent=question.pk)

        self.client.force_login(self.taro)
        self.client.post(reverse("washoku:comment_delete", args=[question.pk]))

        question.refresh_from_db()
        self.assertTrue(question.is_deleted)
        self.assertContains(
            self.client.get(reverse("washoku:recipe_detail", args=[self.recipe.pk])),
            "このコメントは削除されました",
        )

    def test_three_reports_hide_a_comment(self):

        self.post_comment(self.taro)
        comment = Comment.objects.get()

        for name in ["a", "b", "c"]:
            user = get_user_model().objects.create_user(name, password="x")
            self.client.force_login(user)
            self.client.post(reverse("washoku:comment_report", args=[comment.pk]))

        comment.refresh_from_db()
        self.assertTrue(comment.is_hidden)

    def test_visitors_cannot_post(self):

        self.client.post(self.url, {"kind": "tip", "body": "test"})

        self.assertFalse(Comment.objects.exists())


class StoreTests(TestCase):

    def setUp(self):
        self.store = Store.objects.create(
            name="Nishi Japan Shop",
            kind="japanese",
            address="Seefeldstrasse 12, 8008 Zürich",
        )
        self.user = get_user_model().objects.create_user("taro", password="x")

    def test_import_stores_updates_instead_of_duplicating(self):

        stores = [{
            "name": "Nishi Japan Shop",
            "kind": "japanese",
            "address": "Seefeldstrasse 12, 8008 Zürich",
            "opening_hours": "月〜金 10:00–18:30",
        }]

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stores.json"
            path.write_text(json.dumps(stores), encoding="utf-8")
            with mock.patch("washoku.geocode.lookup", return_value=(47.36, 8.55)) as lookup:
                call_command("import_washoku", stores=str(path), stdout=open("/dev/null", "w"))

        store = Store.objects.get()
        self.assertEqual(store.opening_hours, "月〜金 10:00–18:30")
        self.assertEqual((store.latitude, store.longitude), (47.36, 8.55))
        lookup.assert_called_once_with("Seefeldstrasse 12, 8008 Zürich")

    def test_moved_store_is_located_again(self):

        self.store.latitude, self.store.longitude = 1.0, 2.0
        self.store.save()

        stores = [{"name": "Nishi Japan Shop", "kind": "japanese", "address": "Falkenstrasse 26, 8008 Zürich"}]

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stores.json"
            path.write_text(json.dumps(stores), encoding="utf-8")

            with mock.patch("washoku.geocode.lookup", return_value=(47.37, 8.54)):
                call_command("import_washoku", stores=str(path), stdout=open("/dev/null", "w"))

        self.store.refresh_from_db()
        self.assertEqual(self.store.address, "Falkenstrasse 26, 8008 Zürich")
        self.assertEqual((self.store.latitude, self.store.longitude), (47.37, 8.54))

    def test_geocoder_reads_the_swisstopo_answer(self):

        from io import BytesIO

        from .geocode import clean_address, lookup

        answer = BytesIO(json.dumps({"results": [{"attrs": {"lat": 47.3, "lon": 8.5}}]}).encode())

        with mock.patch("washoku.geocode.urlopen", return_value=answer):
            self.assertEqual(lookup("Zwinglistrasse 11, 8004 Zürich"), (47.3, 8.5))

        with mock.patch("washoku.geocode.urlopen", side_effect=OSError("offline")):
            self.assertIsNone(lookup("Zwinglistrasse 11, 8004 Zürich"))

        self.assertEqual(clean_address("Zwinglistrasse 11 (Hinterhof), 8004 Zürich"), "Zwinglistrasse 11 , 8004 Zürich")

    def test_store_list_has_coordinates_for_near_me(self):

        self.store.latitude, self.store.longitude = 47.3601, 8.5512
        self.store.save()

        response = self.client.get(reverse("washoku:store_list"))

        self.assertContains(response, 'data-lat="47.360100"')
        self.assertContains(response, "現在地から近い順")

    def test_store_review_shows_on_the_store_and_home(self):

        self.client.force_login(self.user)
        self.client.post(
            reverse("washoku:comment_create", args=["store", self.store.pk]),
            {"kind": "tip", "body": "納豆の品ぞろえが多い"},
        )

        comment = Comment.objects.get()
        self.assertEqual(comment.store, self.store)
        self.assertEqual(
            comment.get_absolute_url(),
            reverse("washoku:store_detail", args=[self.store.pk]) + f"#comment-{comment.pk}",
        )

        self.assertContains(self.client.get(reverse("washoku:store_detail", args=[self.store.pk])), "納豆の品ぞろえ")
        self.assertContains(self.client.get(reverse("washoku:store_list")), "口コミ 1件")
        self.assertContains(self.client.get(reverse("washoku:home")), comment.get_absolute_url())

    def test_hidden_stores_are_not_shown(self):

        self.store.is_active = False
        self.store.save()

        self.assertNotContains(self.client.get(reverse("washoku:store_list")), "Nishi Japan Shop")
        self.assertEqual(self.client.get(reverse("washoku:store_detail", args=[self.store.pk])).status_code, 404)


class AboutAndMyPageTests(TestCase):

    def test_feedback_is_saved_once_per_minute(self):

        url = reverse("washoku:about")

        self.client.post(url, {"message": "納豆のレシピがほしい"})
        self.client.post(url, {"message": "もう一通"})

        self.assertEqual(list(Feedback.objects.values_list("message", flat=True)), ["納豆のレシピがほしい"])

    def test_bots_filling_the_hidden_field_are_ignored(self):

        self.client.post(reverse("washoku:about"), {"message": "spam", "website": "http://spam.example"})

        self.assertFalse(Feedback.objects.exists())

    def test_visitors_see_my_page_but_lists_need_login(self):

        # マイページはテーマ切り替えとログイン案内のため誰でも開ける
        self.assertContains(self.client.get(reverse("washoku:my_page")), "washoku-theme-toggle")

        for name in ["family_favorites", "my_notes", "my_comments"]:
            response = self.client.get(reverse(f"washoku:{name}"))
            self.assertEqual(response.status_code, 302, name)

        # お気に入りはレシピのタブなので、ログインしていなくても開けて登録の案内が出る
        response = self.client.get(reverse("washoku:my_favorites"))
        self.assertContains(response, "お気に入りの保存は")
        self.assertContains(response, "レシピを探す")

    def test_menu_and_tabs(self):

        home = self.client.get(reverse("washoku:home"))
        self.assertContains(home, "<span>コミュニティ</span>", html=True)
        self.assertContains(home, "<span>マイページ</span>", html=True)
        self.assertNotContains(home, "<span>お店</span>", html=True)

        stores = self.client.get(reverse("washoku:store_list"))
        for label in ["食材", "代わり", "お店"]:
            self.assertContains(stores, f">{label}</a>")
        self.assertNotContains(stores, ">おすすめ</a>")

        # コミュニティは 質問・口コミ・コラム・アンケート (参考リンクはコラムの中)
        community = self.client.get(reverse("washoku:question_list"))
        for label in ["質問", "口コミ", "コラム", "アンケート"]:
            self.assertContains(community, f">{label}</a>")
        self.assertNotContains(community, ">リンク</a>")

        # タブのあるページは、左右のスワイプでも移れる
        self.assertContains(stores, "washoku/swipe_tabs")

    def test_my_pages_list_favorites_and_comments(self):

        user = get_user_model().objects.create_user("taro", password="x")
        recipe = make_recipe()
        RecipeRating.objects.create(user=user, recipe=recipe, rating=5)
        Comment.objects.create(author=user, recipe=recipe, kind="tip", body="みりんは少なめが好き")

        self.client.force_login(user)

        self.assertEqual(self.client.get(reverse("washoku:my_page")).status_code, 200)
        self.assertContains(self.client.get(reverse("washoku:my_favorites")), recipe.name)
        self.assertContains(self.client.get(reverse("washoku:my_favorites")), reverse("washoku:family"))
        self.assertContains(self.client.get(reverse("washoku:family_favorites"), follow=True), "家族を招待する")
        self.assertContains(self.client.get(reverse("washoku:my_comments")), "みりんは少なめが好き")


class RecipeSubmissionTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user("hanako", password="x")
        self.url = reverse("washoku:recipe_submit")
        make_recipe()  # 鶏もも肉・醤油などの食材を用意する

    def submit(self, **data):
        self.client.force_login(self.user)
        return self.client.post(
            self.url,
            {
                "name": "鶏のさっぱり煮",
                "category": "meat",
                "description": "お酢でさっぱり",
                "cooking_time_minutes": "25",
                "servings": "2",
                "ingredients_text": "鶏もも肉 300g\n醤油：大さじ2\nりんご酢 大さじ3",
                "steps": "鶏肉を切る\n\n調味料と煮る",
                "swiss_tips": "",
                **data,
            },
        )

    def test_visitors_must_log_in(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_submission_is_a_hidden_draft_until_published(self):

        with mock.patch("washoku.views.send_admin_alert") as alert:
            response = self.submit()

        recipe = Recipe.objects.get(name="鶏のさっぱり煮")

        self.assertRedirects(response, reverse("washoku:recipe_detail", args=[recipe.pk]))
        self.assertEqual((recipe.status, recipe.origin, recipe.submitted_by), ("draft", "member", self.user))
        self.assertEqual(recipe.steps, "鶏肉を切る\n調味料と煮る")
        self.assertIn("りんご酢", recipe.submitted_ingredients)
        alert.assert_called_once()

        # 食材リストにある材料だけ自動でつながる
        linked = dict(recipe.recipe_ingredients.values_list("ingredient__name", "amount"))
        self.assertEqual(linked, {"鶏もも肉": "300g", "醤油": "大さじ2"})

        # 投稿した本人には見えるが、ほかの人には見えない
        self.assertContains(self.client.get(reverse("washoku:recipe_detail", args=[recipe.pk])), "確認待ち")
        self.assertContains(self.client.get(reverse("washoku:my_recipes")), "鶏のさっぱり煮")

        self.client.logout()
        self.assertEqual(self.client.get(reverse("washoku:recipe_detail", args=[recipe.pk])).status_code, 404)

        recipe.status = "published"
        recipe.save()
        self.assertContains(self.client.get(reverse("washoku:recipe_detail", args=[recipe.pk])), "hanako さんのレシピ")

    def test_duplicate_name_is_refused(self):

        response = self.submit(name="照り焼きチキン")

        self.assertContains(response, "同じ名前のレシピがもうあります")
        self.assertFalse(Recipe.objects.filter(submitted_by=self.user).exists())

    def test_too_many_pending_submissions(self):

        for number in range(5):
            Recipe.objects.create(name=f"確認待ち{number}", steps="x", submitted_by=self.user)

        self.client.force_login(self.user)
        self.assertRedirects(self.client.get(self.url), reverse("washoku:my_recipes"))


class MenuTests(TestCase):

    def test_phone_tabbar_has_community_and_my_page(self):

        html = self.client.get(reverse("washoku:home")).content.decode()
        tabbar = html[html.index('class="washoku-tabbar"'):]

        self.assertIn(reverse("washoku:poll_list"), tabbar)
        self.assertIn(reverse("washoku:my_page"), tabbar)
        self.assertNotIn(reverse("washoku:store_list"), tabbar)
        self.assertIn('class="washoku-me', html)
        self.assertNotIn("家庭料理のレシピ集です", html)


class AdminAttentionTests(TestCase):

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user("admin", password="x", is_staff=True, is_superuser=True)
        self.member = User.objects.create_user("hanako", password="x")
        self.recipe = make_recipe()
        self.store = Store.objects.create(name="Nishi", kind="japanese", address="Seefeldstrasse 12, 8008 Zürich")

    def attention(self):
        from portal.context_processors import admin_attention_counts

        request = self.client.get(reverse("washoku:home")).wsgi_request
        request.user = self.admin
        return admin_attention_counts(request)["admin_attention"]

    def test_washoku_items_are_counted_by_where_they_came_from(self):

        Comment.objects.create(author=self.member, recipe=self.recipe, kind="tip", body="a")
        Comment.objects.create(author=self.member, recipe=self.recipe, kind="question", body="b")
        Comment.objects.create(author=self.member, store=self.store, kind="tip", body="c")
        Comment.objects.create(author=self.member, store=self.store, kind="tip", body="d", admin_checked=True)
        Recipe.objects.create(name="投稿", steps="x", origin="member", submitted_by=self.member)
        Feedback.objects.create(message="要望")

        attention = self.attention()
        washoku = next(group for group in attention["groups"] if group["app"] == "スイスで和食")
        counts = {item["label"]: item["count"] for item in washoku["items"]}

        self.assertEqual(counts, {"投稿レシピ": 1, "レシピへのコメント": 2, "お店の口コミ": 1, "質問箱": 1})
        self.assertEqual(attention["total"], 5)

        Post.objects.create(kind="column", title="薄切り肉", body="x" * 20, author=self.member)
        published = Post.objects.create(kind="product", title="冷凍餃子", body="x" * 20, shop="migros", status="published")
        Comment.objects.create(author=self.member, post=published, kind="tip", body="おいしい")

        washoku = next(group for group in self.attention()["groups"] if group["app"] == "スイスで和食")
        counts = {item["label"]: item["count"] for item in washoku["items"]}

        self.assertEqual(counts["コラム・商品の投稿"], 1)
        self.assertEqual(counts["コラム・商品へのコメント"], 1)

    def test_admins_own_comments_are_not_pending(self):

        self.client.force_login(self.admin)
        self.client.post(
            reverse("washoku:comment_create", args=["recipe", self.recipe.pk]),
            {"kind": "tip", "body": "管理者から"},
        )

        self.assertTrue(Comment.objects.get().admin_checked)
        self.assertEqual(self.attention()["groups"], [])

    def test_admin_bar_links_to_filtered_list(self):

        Comment.objects.create(author=self.member, store=self.store, kind="tip", body="口コミ")

        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin:index"))

        self.assertContains(response, "お店の口コミ")
        self.assertContains(response, "admin_checked__exact=0&amp;target=store")
        self.assertContains(
            self.client.get(reverse("admin:washoku_comment_changelist") + "?admin_checked__exact=0&target=store"),
            "お店: Nishi",
        )


class IngredientGermanNameTests(TestCase):

    def test_recipe_ingredients_show_the_german_name(self):

        recipe = make_recipe()
        Ingredient.objects.filter(name="鶏もも肉").update(name_de="Pouletschenkel")
        Ingredient.objects.filter(name="醤油").update(name="醤油（Sojasauce）", name_de="Sojasauce")

        response = self.client.get(reverse("washoku:recipe_detail", args=[recipe.pk]))

        self.assertContains(response, "（Pouletschenkel）")
        # 名前にもうドイツ語が入っているときは重ねて書かない
        self.assertNotContains(response, "（Sojasauce）</small>")


class TrialAccessTests(TestCase):
    """
    一般公開前のテスト運用: URL を知っている人は、ログインしていてもいなくても見られる。
    """

    def setUp(self):
        self.recipe = make_recipe()
        self.urls = [
            reverse("washoku:home"),
            reverse("washoku:recipe_detail", args=[self.recipe.pk]),
            reverse("washoku:store_list"),
        ]

    def assert_can_view(self):
        for url in self.urls:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_visitors_without_login(self):
        self.assert_can_view()

    def test_public_signup_members(self):
        from django.contrib.auth.models import Group

        from portal.middleware import PUBLIC_USER_GROUP

        user = get_user_model().objects.create_user("friend", password="x")
        user.groups.add(Group.objects.get_or_create(name=PUBLIC_USER_GROUP)[0])
        self.client.force_login(user)

        self.assert_can_view()

    def test_search_engines_can_be_turned_off(self):

        with self.settings(WASHOKU_ALLOW_SEARCH_ENGINES=False):
            self.assertContains(self.client.get(self.urls[0]), '<meta name="robots" content="noindex, nofollow">')

        with self.settings(WASHOKU_ALLOW_SEARCH_ENGINES=True):
            self.assertNotContains(self.client.get(self.urls[0]), 'name="robots"')


class NutritionTests(TestCase):

    def test_recipe_shows_nutrition_and_pfc_balance(self):

        recipe = make_recipe(energy_kcal=340, protein_g=28, fat_g=20, carbs_g=12, salt_g=2.6)

        self.assertEqual(recipe.pfc_ratio(), {"protein": 33, "fat": 53, "carbs": 14})

        response = self.client.get(reverse("washoku:recipe_detail", args=[recipe.pk]))

        self.assertContains(response, "1人分（1食分）の栄養")
        self.assertContains(response, "340<small>kcal</small>")
        self.assertContains(response, "P 33% ・ F 53% ・ C 14%")

    def test_recipe_without_nutrition_hides_the_box(self):

        recipe = make_recipe()

        self.assertIsNone(recipe.pfc_ratio())
        self.assertNotContains(
            self.client.get(reverse("washoku:recipe_detail", args=[recipe.pk])),
            "1人分（1食分）の栄養",
        )

    def test_recipes_can_be_sorted_by_energy(self):

        make_recipe("重い料理", energy_kcal=900, protein_g=1, fat_g=1, carbs_g=1)
        make_recipe("軽い料理", energy_kcal=100, protein_g=1, fat_g=1, carbs_g=1)
        make_recipe("不明な料理")

        html = self.client.get(reverse("washoku:recipe_list") + "?sort=light").content.decode()

        self.assertLess(html.index("軽い料理"), html.index("重い料理"))
        self.assertLess(html.index("重い料理"), html.index("不明な料理"))

    def test_find_by_nutrition_filters_and_sorts(self):

        make_recipe("鶏むね", energy_kcal=350, protein_g=32, fat_g=6, carbs_g=10, salt_g=1.5)
        make_recipe("豚汁", energy_kcal=250, protein_g=12, fat_g=10, carbs_g=20, salt_g=2.8)
        make_recipe("カツ丼", energy_kcal=850, protein_g=30, fat_g=30, carbs_g=100, salt_g=3.5)
        make_recipe("不明な料理")

        url = reverse("washoku:find_by_nutrition")

        html = self.client.get(url).content.decode()
        self.assertNotIn("不明な料理", html)
        self.assertLess(html.index("豚汁"), html.index("鶏むね"))

        html = self.client.get(url + "?protein=20&sort=protein").content.decode()
        self.assertLess(html.index("鶏むね"), html.index("カツ丼"))
        self.assertNotIn("豚汁", html)
        self.assertIn("P 32g", html)

        response = self.client.get(url + "?kcal=400&salt=2")
        self.assertContains(response, "鶏むね")
        self.assertNotContains(response, "豚汁")
        self.assertNotContains(response, "カツ丼")

        # 選べない値は無視する
        self.assertContains(self.client.get(url + "?kcal=abc&sort=zzz"), "カツ丼")

    def test_home_offers_three_ways_and_random(self):

        response = self.client.get(reverse("washoku:home"))

        self.assertContains(response, reverse("washoku:find_by_nutrition"))
        self.assertContains(response, reverse("washoku:find_by_ingredients"))
        self.assertContains(response, "washoku-picker-random")
        self.assertContains(response, "今日のごはん、何にする？")
        # 検索はヘッダーにあるので、HOME の検索欄はなし
        self.assertNotContains(response, 'placeholder="料理、食材、お店などを探す"')
        self.assertNotContains(response, "<h2>みんなの知恵")

        response = self.client.get(reverse("washoku:recipe_list"))
        self.assertContains(response, "ほかの探し方")
        self.assertContains(response, reverse("washoku:my_favorites"))


class PostTests(TestCase):

    def setUp(self):
        User = get_user_model()
        self.member = User.objects.create_user("hanako", password="x")
        self.other = User.objects.create_user("taro", password="x")
        self.admin = User.objects.create_user("admin", password="x", is_staff=True)

    def test_member_column_waits_for_approval(self):

        self.client.force_login(self.member)

        with mock.patch("washoku.views.send_admin_alert") as alert:
            response = self.client.post(
                reverse("washoku:post_submit", args=["column"]),
                {"title": "肉屋さんで薄切り肉を頼むコツ", "body": "「dünn geschnitten, bitte」と言うと切ってくれます。"},
            )

        post = Post.objects.get()

        self.assertRedirects(response, post.get_absolute_url())
        self.assertEqual((post.kind, post.status, post.author), ("column", "draft", self.member))
        alert.assert_called_once()

        # 本人には見える、ほかの人と一覧には出ない
        self.assertContains(self.client.get(post.get_absolute_url()), "確認待ち（あなたにだけ表示）")
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(post.get_absolute_url()).status_code, 404)
        self.assertNotContains(self.client.get(reverse("washoku:column_list")), "薄切り肉")

        post.status = "published"
        post.save()

        self.assertContains(self.client.get(reverse("washoku:column_list")), "薄切り肉")
        self.assertContains(self.client.get(reverse("washoku:activity")), "薄切り肉")

    def test_review_needs_a_verdict_and_shows_on_its_ingredient(self):

        self.client.force_login(self.member)
        ingredient = Ingredient.objects.create(name="ごぼう", category="vegetable")
        url = reverse("washoku:post_submit", args=["product"])

        response = self.client.post(url, {"title": "冷凍ごぼう", "shops": ["coop"], "body": "香りがほとんどなかったです。"})
        self.assertContains(response, "どうだった？")
        self.assertFalse(Post.objects.exists())

        page = self.client.get(url + f"?ingredient={ingredient.pk}")
        self.assertContains(page, f'name="ingredient" value="{ingredient.pk}"')

        self.client.post(
            url,
            {"title": "冷凍ごぼう", "verdict": "bad", "shops": ["coop"], "body": "香りがほとんどなかったです。", "ingredient": ingredient.pk},
        )
        review = Post.objects.get()
        self.assertEqual(review.verdict, "bad")
        # 口コミは確認なしですぐ載る
        self.assertEqual(review.status, "published")
        self.assertEqual(list(review.ingredients.all()), [ingredient])

        review.status = "published"
        review.save()

        detail = self.client.get(reverse("washoku:ingredient_detail", args=[ingredient.pk]))
        self.assertContains(detail, "みんなの口コミ")
        self.assertContains(detail, "👎 いまいちだった")
        self.assertContains(detail, "冷凍ごぼう")

        list_url = reverse("washoku:product_list")
        self.assertContains(self.client.get(list_url + "?verdict=bad"), "冷凍ごぼう")
        self.assertNotContains(self.client.get(list_url + "?verdict=good"), "冷凍ごぼう")
        # 口コミはコミュニティのタブ
        self.assertContains(self.client.get(list_url), ">口コミ</a>")

    def test_store_review_from_the_store_page(self):

        self.client.force_login(self.member)
        store = Store.objects.create(name="Yoshi Market", kind="japanese", city="Zürich")
        url = reverse("washoku:post_submit", args=["product"])

        page = self.client.get(url + f"?store={store.pk}")
        self.assertContains(page, 'id="id_about_1" checked')
        self.assertContains(self.client.get(reverse("washoku:store_detail", args=[store.pk])), f"?store={store.pk}")

        response = self.client.post(url, {"about": "store", "verdict": "good", "body": "店員さんが親切で、品ぞろえも多いです。"})
        self.assertContains(response, "お店を選んでください。")

        self.client.post(url, {"about": "store", "store": store.pk, "verdict": "good", "body": "店員さんが親切で、品ぞろえも多いです。"})
        review = Post.objects.get()
        self.assertEqual((review.title, review.store, review.shop), ("Yoshi Market", store, ""))

        review.status = "published"
        review.save()

        detail = self.client.get(reverse("washoku:store_detail", args=[store.pk]))
        self.assertContains(detail, "店員さんが親切で")
        self.assertContains(detail, "🏪 お店")
        self.assertContains(self.client.get(reverse("washoku:product_list")), "Yoshi Market")

    def test_product_needs_a_shop_and_can_be_filtered(self):

        self.client.force_login(self.member)
        url = reverse("washoku:post_submit", args=["product"])

        response = self.client.post(url, {"title": "冷凍ギョーザ", "body": "日本の味にかなり近いです。"})
        self.assertContains(response, "このフィールドは必須です")

        self.client.post(
            url,
            {"title": "冷凍ギョーザ", "verdict": "good", "shops": ["migros", "coop"], "section": "frozen", "resembles": "冷凍餃子", "body": "日本の味にかなり近いです。"},
        )
        Post.objects.update(status="published")

        self.assertEqual(Post.objects.get().shop_labels(), ["Migros", "Coop"])
        self.assertEqual(Post.objects.get().verdict, "good")

        list_url = reverse("washoku:product_list")
        self.assertContains(self.client.get(list_url + "?shop=migros"), "冷凍ギョーザ")
        self.assertContains(self.client.get(list_url + "?shop=migros"), "冷凍餃子に近い")
        self.assertContains(self.client.get(list_url + "?shop=coop"), "冷凍ギョーザ")
        self.assertNotContains(self.client.get(list_url + "?shop=denner"), "冷凍ギョーザ")
        self.assertNotContains(self.client.get(reverse("washoku:column_list")), "冷凍ギョーザ")

    def test_scheduled_column_is_published_when_its_time_comes(self):

        from washoku import middleware

        later = timezone.now() + timedelta(hours=2)
        post = Post.objects.create(
            kind="column", title="予約したコラム", body="x" * 20, author=self.admin, publish_at=later,
        )
        unscheduled = Post.objects.create(kind="column", title="確認待ち", body="x" * 20, author=self.member)

        middleware._last_check = 0
        self.assertNotContains(self.client.get(reverse("washoku:column_list")), "予約したコラム")

        with mock.patch("django.utils.timezone.now", return_value=later + timedelta(minutes=1)):
            middleware._last_check = 0
            self.assertContains(self.client.get(reverse("washoku:column_list")), "予約したコラム")

        post.refresh_from_db()
        unscheduled.refresh_from_db()
        self.assertEqual((post.status, post.created_at), ("published", later))
        self.assertEqual(unscheduled.status, "draft")

    def test_columns_and_recipes_link_through_ingredient_groups(self):

        recipe = make_recipe()
        thigh = Ingredient.objects.get(name="鶏もも肉")
        breast = Ingredient.objects.create(name="鶏むね肉", search_group="鶏肉", category="meat")

        column = Post.objects.create(kind="column", title="鶏肉の部位の選び方", body="x" * 20, author=self.member, status="published")
        column.ingredients.add(breast)
        draft = Post.objects.create(kind="column", title="下書きのコラム", body="x" * 20, author=self.member)
        draft.ingredients.add(thigh)

        # 同じ検索グループ (鶏肉) のレシピと食材のページに出る。下書きは出ない
        page = self.client.get(reverse("washoku:recipe_detail", args=[recipe.pk]))
        self.assertContains(page, "関連する読みもの")
        self.assertContains(page, "鶏肉の部位の選び方")
        self.assertNotContains(page, "下書きのコラム")
        self.assertContains(self.client.get(reverse("washoku:ingredient_detail", args=[thigh.pk])), "鶏肉の部位の選び方")

        page = self.client.get(column.get_absolute_url())
        self.assertContains(page, "関連レシピ")
        self.assertContains(page, "照り焼きチキン")

    def test_serving_unit_labels(self):

        bread = make_recipe(name="メロンパン", servings=8, serving_unit="個", energy_kcal=280, protein_g=6, fat_g=8, carbs_g=45)
        dish = make_recipe(name="肉じゃが", servings=4, energy_kcal=330, protein_g=14, fat_g=12, carbs_g=40)

        page = self.client.get(reverse("washoku:recipe_detail", args=[bread.pk]))
        self.assertContains(page, "8個分")
        self.assertContains(page, "1個あたりの栄養")

        page = self.client.get(reverse("washoku:recipe_detail", args=[dish.pk]))
        self.assertContains(page, "4人分")
        self.assertContains(page, "1人分（1食分）の栄養")

    def test_staff_posts_are_published_at_once(self):

        self.client.force_login(self.admin)
        self.client.post(
            reverse("washoku:post_submit", args=["column"]),
            {"title": "お知らせ", "body": "コラムを書いてみてください。"},
        )

        self.assertEqual(Post.objects.get().status, "published")

    def test_comments_on_published_posts_only(self):

        draft = Post.objects.create(kind="column", title="下書き", body="x" * 20, author=self.member)
        post = Post.objects.create(kind="column", title="公開", body="x" * 20, author=self.member, status="published")

        self.client.force_login(self.other)

        self.assertEqual(
            self.client.post(reverse("washoku:comment_create", args=["post", draft.pk]), {"kind": "tip", "body": "a"}).status_code,
            404,
        )

        response = self.client.post(reverse("washoku:comment_create", args=["post", post.pk]), {"kind": "question", "body": "どこの肉屋ですか？"})
        comment = Comment.objects.get()

        self.assertRedirects(response, comment.get_absolute_url())
        self.assertEqual(comment.post, post)
        self.assertContains(self.client.get(reverse("washoku:question_list")), "どこの肉屋ですか？")

    def test_post_by_deleted_member_still_renders(self):

        post = Post.objects.create(kind="column", title="古い記事", body="x" * 20, author=self.member, status="published")
        self.member.delete()

        self.assertContains(self.client.get(Post.objects.get(pk=post.pk).get_absolute_url()), "退会した会員")

    def test_pending_limit(self):

        for number in range(5):
            Post.objects.create(kind="column", title=f"下書き{number}", body="x" * 20, author=self.member)

        self.client.force_login(self.member)

        self.assertRedirects(
            self.client.get(reverse("washoku:post_submit", args=["column"])),
            reverse("washoku:my_posts"),
        )
        self.assertEqual(
            self.client.get(reverse("washoku:post_submit", args=["product"])).status_code,
            200,
        )

    def test_member_link_needs_url_and_shows_source(self):

        self.client.force_login(self.member)
        url = reverse("washoku:post_submit", args=["link"])

        response = self.client.post(url, {"title": "食材探しの記事", "body": "Coop で買える日本の食材の話です。"})
        self.assertContains(response, "このフィールドは必須です")

        # URL だけでも投稿できる (タイトルはひとまずサイト名)
        with mock.patch("washoku.views.send_admin_alert"):
            self.client.post(url, {"url": "https://blog.example.ch/post/1"})

        only_url = Post.objects.get()
        self.assertEqual((only_url.title, only_url.body), ("blog.example.ch", ""))
        only_url.delete()

        with mock.patch("washoku.views.send_admin_alert"):
            self.client.post(
                url,
                {
                    "title": "食材探しの記事",
                    "url": "https://example.com/article",
                    "source": "例のブログ（2025年）",
                    "body": "Coop で買える日本の食材の話です。",
                },
            )

        post = Post.objects.get()
        self.assertEqual((post.kind, post.status), ("link", "draft"))

        post.status = "published"
        post.save()

        # 参考リンクはコラムの一覧に「リンク」として並ぶ (古い URL はコラムへ)
        self.assertRedirects(self.client.get(reverse("washoku:link_list")), reverse("washoku:column_list"))
        links = self.client.get(reverse("washoku:column_list"))
        self.assertContains(links, "食材探しの記事")
        self.assertNotContains(links, "Coop で買える日本の食材の話です。")
        self.assertContains(links, '<span class="washoku-chip">リンク</span>')

        detail = self.client.get(post.get_absolute_url())
        self.assertContains(detail, 'href="https://example.com/article"')
        self.assertContains(detail, "元の記事を読む")
        self.assertContains(detail, "紹介: hanako さん")

    def test_import_adds_reference_links_once(self):

        get_user_model().objects.create_superuser("owner", password="x")

        for _ in range(2):
            call_command("import_washoku", "--new-only", "--no-geocode", stdout=open("/dev/null", "w"))

        links = Post.objects.filter(kind="link")

        self.assertEqual(links.count(), 4)
        self.assertEqual(links.filter(status="published").count(), 4)
        self.assertEqual(set(links.values_list("author__username", flat=True)), {"owner"})
        self.assertTrue(all(link.source for link in links))


class SeasonDesignTests(TestCase):

    def test_halloween_design_follows_the_date_and_the_admin_setting(self):

        from datetime import date

        from .models import DisplaySettings

        display = DisplaySettings.load()

        self.assertEqual(display.season(date(2026, 10, 25)), "halloween")
        self.assertEqual(display.season(date(2026, 10, 10)), "")
        self.assertEqual(display.season(date(2026, 11, 1)), "")

        display.home_season = "none"
        self.assertEqual(display.season(date(2026, 10, 25)), "")

        display.home_season = "halloween"
        display.save()
        self.assertEqual(display.season(date(2026, 5, 1)), "halloween")
        self.assertContains(self.client.get(reverse("washoku:home")), "Trick or Treat!")

        display.home_season = "none"
        display.save()
        self.assertNotContains(self.client.get(reverse("washoku:home")), "Trick or Treat!")


class SubstituteListTests(TestCase):

    def test_shishito_and_satsumaimo_are_not_substitutes_any_more(self):

        import importlib

        from django.apps import apps

        seeded = json.loads((Path(__file__).parent / "data" / "ingredients.json").read_text())
        names = json.dumps(seeded, ensure_ascii=False)
        kohlrabi = Ingredient.objects.create(name="コールラビ", category="vegetable")
        for name in ("ししとう", "さつまいも", "かぶ"):
            Substitute.objects.create(original_name=name, substitute=kohlrabi)

        importlib.import_module("washoku.migrations.0044_remove_shishito_satsumaimo_substitutes").remove_substitutes(apps, None)

        self.assertEqual(list(Substitute.objects.values_list("original_name", flat=True)), ["かぶ"])
        self.assertNotIn('"original_name": "ししとう"', names)
        self.assertNotIn('"original_name": "さつまいも"', names)

    def test_lists_japanese_vegetables_and_their_swiss_substitutes(self):

        kohlrabi = Ingredient.objects.create(name="コールラビ", name_de="Kohlrabi", category="vegetable")
        Substitute.objects.create(original_name="かぶ", substitute=kohlrabi, tips="薄めに切る。")

        response = self.client.get(reverse("washoku:substitute_list"))

        self.assertContains(response, "かぶ")
        self.assertContains(response, "コールラビ</a>")
        self.assertContains(response, "Kohlrabi")
        self.assertContains(response, "薄めに切る。")

    def test_member_suggestion_waits_for_approval_and_links_known_ingredients(self):

        kohlrabi = Ingredient.objects.create(name="コールラビ", name_de="Kohlrabi", category="vegetable")
        member = get_user_model().objects.create_user("hanako", password="x")
        self.client.force_login(member)

        with mock.patch("washoku.views.send_admin_alert") as alert:
            self.client.post(
                reverse("washoku:substitute_submit"),
                {"original_name": "かぶ", "swiss_name": "kohlrabi", "tips": "薄く切る"},
            )
            self.client.post(
                reverse("washoku:substitute_submit"),
                {"original_name": "春菊", "swiss_name": "Rucola", "tips": ""},
            )

        linked, free = Substitute.objects.order_by("pk")

        self.assertEqual((linked.substitute, linked.status, linked.submitted_by), (kohlrabi, "draft", member))
        self.assertEqual((free.substitute, free.substitute_name), (None, "Rucola"))
        self.assertEqual(alert.call_count, 2)

        page = reverse("washoku:substitute_list")
        self.assertNotContains(self.client.get(page), "Rucola")
        self.assertNotContains(self.client.get(reverse("washoku:ingredient_detail", args=[kohlrabi.pk])), "「かぶ」の代わりに")

        Substitute.objects.update(status="published")

        response = self.client.get(page)
        self.assertContains(response, "Rucola")
        self.assertContains(response, "みんなが見つけた代用品")
        self.assertContains(response, "hanako さんが教えてくれました")
        self.assertContains(self.client.get(page + "?q=春菊"), "Rucola")
        self.assertNotContains(self.client.get(page + "?q=春菊"), "コールラビ</a>")

        # 同じ組み合わせは二重に登録しない
        response = self.client.post(
            reverse("washoku:substitute_submit"),
            {"original_name": "春菊", "swiss_name": "Rucola", "tips": ""},
        )
        self.assertContains(response, "もう登録されています")
        self.assertEqual(Substitute.objects.count(), 2)


class SearchAndActivityTests(TestCase):

    def setUp(self):
        self.member = get_user_model().objects.create_user("hanako", password="x")
        self.recipe = make_recipe()

    def test_search_covers_the_whole_app(self):

        Store.objects.create(name="Lian Hua", kind="asian", address="Förrlibuckstrasse 30, 8005 Zürich")
        Post.objects.create(kind="column", title="照り焼きのコツ", body="x" * 20, status="published")
        Post.objects.create(kind="column", title="照り焼きの下書き", body="x" * 20)
        Comment.objects.create(author=self.member, recipe=self.recipe, kind="tip", body="照り焼きは弱火で")

        response = self.client.get(reverse("washoku:search") + "?q=照り焼き")

        self.assertContains(response, "照り焼きチキン")
        self.assertContains(response, "照り焼きのコツ")
        self.assertContains(response, "照り焼きは弱火で")
        self.assertNotContains(response, "照り焼きの下書き")
        self.assertContains(self.client.get(reverse("washoku:search") + "?q=lian"), "Lian Hua")
        self.assertContains(self.client.get(reverse("washoku:search") + "?q=zzz"), "見つかりませんでした")
        self.assertContains(self.client.get(reverse("washoku:home")), reverse("washoku:search"))

    def test_home_shows_fifteen_latest_entries_and_links_to_all(self):

        for number in range(15):
            Comment.objects.create(author=self.member, recipe=self.recipe, kind="tip", body=f"コメント{number:02d}")

        Post.objects.create(kind="product", title="冷凍餃子", body="x" * 20, shop="migros", status="published")

        home = self.client.get(reverse("washoku:home"))

        # 新しい15件 = 商品1件 + コメント14〜01
        self.assertEqual(len(home.context["latest_activity"]), 15)
        self.assertContains(home, "冷凍餃子")
        self.assertContains(home, "コメント01")
        self.assertNotContains(home, "コメント00")
        self.assertContains(home, reverse("washoku:activity"))

        activity = self.client.get(reverse("washoku:activity"))

        self.assertContains(activity, "コメント00")
        self.assertContains(activity, "冷凍餃子")
        html = activity.content.decode()
        self.assertLess(html.index("冷凍餃子"), html.index("コメント03"))


class AnnouncementTests(TestCase):

    def test_latest_active_announcement_is_shown_on_home(self):

        from .models import Announcement

        self.assertNotContains(self.client.get(reverse("washoku:home")), "washoku-announcement-text")

        old = Announcement.objects.create(message="古いお知らせ")
        Announcement.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(hours=1))
        Announcement.objects.create(message="3件目")
        Announcement.objects.create(message="和風洋食を10品追加しました")
        Announcement.objects.create(message="非表示", is_active=False)

        Announcement.objects.create(message="4件目")

        response = self.client.get(reverse("washoku:home"))

        # 新しい3件まで
        self.assertContains(response, "和風洋食を10品追加しました")
        self.assertContains(response, "4件目")
        self.assertNotContains(response, "古いお知らせ")
        self.assertNotContains(response, "非表示")
        self.assertContains(response, "washoku_announcements_closed")

        Announcement.objects.update(created_at=timezone.now() - timedelta(days=30))
        self.assertNotContains(self.client.get(reverse("washoku:home")), "washoku-announcement-text")

    def test_announcement_link_and_no_new_recipes_section(self):

        from .models import Announcement

        Announcement.objects.create(message="本場の洋食を9品追加しました", link="/washoku/recipes/?category=europe")
        response = self.client.get(reverse("washoku:home"))

        self.assertContains(response, 'href="/washoku/recipes/?category=europe"')
        self.assertNotContains(response, "新着レシピ")

    def test_columns_in_home_feed_and_column_page_links_back(self):

        author = get_user_model().objects.create_user("hanako", password="x")
        first = Post.objects.create(kind="column", title="Rahm の選び方", body="x", status="published", author=author)
        Post.objects.create(kind="column", title="下書きのコラム", body="x", status="draft", author=author)
        Post.objects.create(kind="column", title="豆腐の水切り", body="x", status="published", author=author)

        # コラムはカードでなく、みんなの投稿・コメントの中に色付きのタグで出る
        home = self.client.get(reverse("washoku:home"))
        self.assertNotContains(home, "新着コラム")
        self.assertContains(home, "kind-column")
        self.assertContains(home, "Rahm の選び方")
        self.assertNotContains(home, "下書きのコラム")

        page = self.client.get(reverse("washoku:post_detail", args=[first.pk]))
        self.assertContains(page, "みんなのコラムの一覧へ")
        self.assertEqual([post.title for post in page.context["other_columns"]], ["豆腐の水切り"])

    def test_publishing_a_draft_column_moves_it_to_the_top(self):

        staff = get_user_model().objects.create_superuser("owner", password="x")
        old = Post.objects.create(kind="column", title="前に書いたコラム", body="x", status="draft", author=staff)
        Post.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=5))
        Post.objects.create(kind="column", title="昨日のコラム", body="x", status="published", author=staff,
                            created_at=timezone.now() - timedelta(days=1))

        self.client.force_login(staff)
        self.client.post(reverse("admin:washoku_post_changelist"), {"action": "publish", "_selected_action": [old.pk]})

        titles = [post.title for post in self.client.get(reverse("washoku:column_list")).context["posts"]]
        self.assertEqual(titles, ["前に書いたコラム", "昨日のコラム"])


class PushTests(TestCase):

    ENDPOINT = "https://fcm.googleapis.com/fcm/send/abc"

    def setUp(self):
        User = get_user_model()
        self.asker = User.objects.create_user("hanako", password="x")
        self.answerer = User.objects.create_user("taro", password="x")
        self.recipe = make_recipe()

    def subscribe(self, user):
        self.client.force_login(user)
        return self.client.post(
            reverse("washoku:push_subscribe"),
            data=json.dumps({"endpoint": self.ENDPOINT, "keys": {"p256dh": "p", "auth": "a"}}),
            content_type="application/json",
        )

    def test_subscribe_and_unsubscribe(self):

        from .models import PushSubscription

        self.assertEqual(self.subscribe(self.asker).status_code, 200)
        self.assertEqual(PushSubscription.objects.get().user, self.asker)

        self.client.post(
            reverse("washoku:push_unsubscribe"),
            data=json.dumps({"endpoint": self.ENDPOINT}),
            content_type="application/json",
        )
        self.assertFalse(PushSubscription.objects.exists())

        self.client.logout()
        self.assertEqual(
            self.client.post(reverse("washoku:push_subscribe"), data="{}", content_type="application/json").status_code,
            302,
        )

    @mock.patch("washoku.push.is_configured", return_value=True)
    @mock.patch("washoku.push.webpush")
    def test_answer_to_a_question_is_pushed_to_the_asker(self, webpush, _configured):

        self.subscribe(self.asker)
        question = Comment.objects.create(author=self.asker, recipe=self.recipe, kind="question", body="みりんがないときは？")

        self.client.force_login(self.answerer)
        self.client.post(
            reverse("washoku:comment_create", args=["recipe", self.recipe.pk]),
            {"kind": "tip", "body": "白ワインと砂糖で", "parent": question.pk},
        )

        webpush.assert_called_once()
        payload = json.loads(webpush.call_args.kwargs["data"])
        self.assertIn("質問に答えが届きました", payload["title"])
        self.assertIn("白ワインと砂糖で", payload["body"])
        self.assertTrue(payload["url"].startswith(reverse("washoku:recipe_detail", args=[self.recipe.pk])))
        self.assertTrue(Notification.objects.filter(recipient=self.asker).exists())

    @mock.patch("washoku.push.is_configured", return_value=True)
    @mock.patch("washoku.push.webpush", side_effect=Exception("down"))
    def test_push_failure_does_not_break_replies(self, _webpush, _configured):

        self.subscribe(self.asker)
        comment = Comment.objects.create(author=self.asker, recipe=self.recipe, kind="tip", body="a")

        self.client.force_login(self.answerer)
        response = self.client.post(
            reverse("washoku:comment_create", args=["recipe", self.recipe.pk]),
            {"kind": "tip", "body": "返信", "parent": comment.pk},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Comment.objects.count(), 2)

    @mock.patch("washoku.push.is_configured", return_value=True)
    @mock.patch("washoku.push.webpush")
    def test_test_push_and_weekly_switch(self, webpush, _configured):

        from .models import PushSubscription

        self.subscribe(self.asker)
        body = json.dumps({"endpoint": self.ENDPOINT})

        self.assertEqual(self.client.post(reverse("washoku:push_test"), data=body, content_type="application/json").status_code, 200)
        self.assertIn("テスト通知", json.loads(webpush.call_args.kwargs["data"])["title"])

        self.client.post(reverse("washoku:push_weekly"), data=json.dumps({"endpoint": self.ENDPOINT, "weekly": False}), content_type="application/json")
        self.assertFalse(PushSubscription.objects.get().weekly)
        # 送り直しても (アプリを開くたびの同期)、オフのまま
        self.assertFalse(json.loads(self.subscribe(self.asker).content)["weekly"])

        # ほかの人の端末は操作できない
        self.client.force_login(self.answerer)
        self.assertEqual(self.client.post(reverse("washoku:push_test"), data=body, content_type="application/json").status_code, 404)

    def test_push_script_is_on_every_page_for_members(self):

        self.assertNotContains(self.client.get(reverse("washoku:home")), "washoku-push-config")
        self.client.force_login(self.asker)
        self.assertContains(self.client.get(reverse("washoku:home")), "washoku-push-config")
        self.assertContains(self.client.get(reverse("washoku:my_page")), "月曜のお知らせ")


class WeeklyPushTests(TestCase):
    """毎週月曜16時の「今週」のお知らせ"""

    def setUp(self):
        from .models import PushSubscription

        user = get_user_model().objects.create_user("hanako", password="x")
        PushSubscription.objects.create(user=user, endpoint="https://push.example/on", p256dh="p", auth="a")
        PushSubscription.objects.create(user=user, endpoint="https://push.example/off", p256dh="p", auth="a", weekly=False)

    def monday(self, hour):
        from washoku.views import poll_week_start
        return poll_week_start() + timedelta(days=7, hours=hour - 3)

    def make_polls(self, now):
        from washoku.views import poll_week_start

        week_start = poll_week_start(now)
        last = Post.objects.create(kind="poll", title="お米はどこで買う？", status="published")
        Post.objects.filter(pk=last.pk).update(created_at=week_start - timedelta(days=2))
        rice = PollChoice.objects.create(post=last, label="アジア食材店", order=0)
        PollChoice.objects.create(post=last, label="Migros", order=1)
        PollVote.objects.create(post=last, choice=rice, voter_key="a")
        new = Post.objects.create(kind="poll", title="お味噌は何味？", status="published")
        Post.objects.filter(pk=new.pk).update(created_at=week_start + timedelta(hours=1))

    def test_message(self):

        from washoku.weekly_push import weekly_message

        now = self.monday(16)
        self.assertIsNone(weekly_message(now))

        self.make_polls(now)
        title, body = weekly_message(now)
        self.assertEqual(title, "今週のアンケートが始まりました")
        self.assertIn("「アジア食材店」が1位（100%）", body)
        self.assertIn("今週のアンケートは「お味噌は何味？」です。", body)

    @mock.patch("washoku.push.is_configured", return_value=True)
    @mock.patch("washoku.push.webpush")
    def test_sent_once_on_monday_afternoon_to_weekly_devices_only(self, webpush, _configured):

        from washoku.weekly_push import run_if_due

        now = self.monday(16)
        self.make_polls(now)

        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder)
            self.assertFalse(run_if_due(state, now - timedelta(hours=1), write=lambda line: None))
            self.assertFalse(run_if_due(state, now + timedelta(days=1), write=lambda line: None))
            self.assertTrue(run_if_due(state, now, write=lambda line: None))
            self.assertFalse(run_if_due(state, now + timedelta(minutes=1), write=lambda line: None))

        webpush.assert_called_once()
        self.assertEqual(webpush.call_args.kwargs["subscription_info"]["endpoint"], "https://push.example/on")
        self.assertEqual(json.loads(webpush.call_args.kwargs["data"])["url"], "/washoku/?tab=week")


class FavoriteNoteReactionTests(TestCase):

    def setUp(self):
        User = get_user_model()
        self.me = User.objects.create_user("hanako", password="x")
        self.child = User.objects.create_user("ken", password="x")
        self.stranger = User.objects.create_user("other", password="x")
        self.recipe = make_recipe(energy_kcal=340, protein_g=28, fat_g=20, carbs_g=12, salt_g=2.6)
        self.other_recipe = make_recipe("肉じゃが", energy_kcal=330, protein_g=14, fat_g=12, carbs_g=40, salt_g=1.5)

    def test_favorite_toggle_and_sort_by_family_rating(self):

        self.client.force_login(self.me)

        for recipe in (self.recipe, self.other_recipe):
            self.client.post(reverse("washoku:favorite_toggle", args=[recipe.pk]))

        RecipeRating.objects.create(user=self.me, recipe=self.other_recipe, rating=5)

        url = reverse("washoku:my_favorites")

        # 評価した料理が上、♡ だけの料理も出る (前の ?sort=family も評価順)
        for query in ("", "?sort=family"):
            html = self.client.get(url + query).content.decode()
            self.assertLess(html.index("肉じゃが"), html.index("照り焼きチキン"))

        # ★ 評価だけに絞る
        html = self.client.get(url + "?kind=rated").content.decode()
        self.assertIn("肉じゃが", html)
        self.assertNotIn("照り焼きチキン", html)

        self.assertContains(self.client.get(reverse("washoku:recipe_detail", args=[self.recipe.pk])), "保存済み")
        self.client.post(reverse("washoku:favorite_toggle", args=[self.recipe.pk]))
        self.assertEqual(list(RecipeFavorite.objects.values_list("recipe__name", flat=True)), ["肉じゃが"])

    def test_family_favorites_rank_by_family_average_and_stay_private(self):

        from .models import Household, HouseholdMember

        household = Household.objects.create(created_by=self.me)
        HouseholdMember.objects.create(household=household, user=self.me)
        HouseholdMember.objects.create(household=household, user=self.child)

        RecipeRating.objects.create(user=self.me, recipe=self.recipe, rating=3)
        RecipeRating.objects.create(user=self.child, recipe=self.recipe, rating=3)
        RecipeRating.objects.create(user=self.child, recipe=self.other_recipe, rating=5)
        RecipeRating.objects.create(user=self.stranger, recipe=self.recipe, rating=5)

        self.client.force_login(self.me)
        family_url = reverse("washoku:my_favorites") + "?who=family"
        self.assertRedirects(self.client.get(reverse("washoku:family_favorites")), family_url + "&kind=all")
        html = self.client.get(family_url).content.decode()

        self.assertIn("家族みんな", html)
        self.assertLess(html.index("肉じゃが"), html.index("照り焼きチキン"))
        self.assertNotIn("other", html)

        self.assertContains(
            self.client.get(reverse("washoku:recipe_detail", args=[self.recipe.pk])),
            "評価は、あなたと家族のメンバーにだけ見えます",
        )

    def test_family_favorites_show_hearts_of_family_members(self):

        from .models import Household, HouseholdMember

        household = Household.objects.create(created_by=self.me)
        HouseholdMember.objects.create(household=household, user=self.me)
        HouseholdMember.objects.create(household=household, user=self.child)

        RecipeFavorite.objects.create(user=self.child, recipe=self.recipe)
        RecipeFavorite.objects.create(user=self.stranger, recipe=self.other_recipe)

        self.client.force_login(self.me)
        url = reverse("washoku:my_favorites")
        html = self.client.get(url + "?who=family&kind=fav").content.decode()

        self.assertIn("照り焼きチキン", html)
        self.assertIn("♡ ken", html)
        self.assertNotIn("肉じゃが", html)

        # 「わたし」には家族の ♡ は出ない
        self.assertNotIn("照り焼きチキン", self.client.get(url + "?who=me").content.decode())

    def test_private_note(self):

        self.client.force_login(self.me)
        url = reverse("washoku:note_save", args=[self.recipe.pk])

        self.client.post(url, {"body": "みりん多めがよい"})
        self.assertContains(self.client.get(reverse("washoku:recipe_detail", args=[self.recipe.pk])), "みりん多めがよい")
        self.assertContains(self.client.get(reverse("washoku:my_notes")), "みりん多めがよい")

        self.client.force_login(self.child)
        self.assertNotContains(self.client.get(reverse("washoku:recipe_detail", args=[self.recipe.pk])), "みりん多めがよい")

        self.client.force_login(self.me)
        self.client.post(url, {"body": "  "})
        self.assertFalse(RecipeNote.objects.exists())

    def test_like_and_thanks_on_comments(self):

        answer = Comment.objects.create(author=self.child, recipe=self.recipe, kind="tip", body="白ワインで代用できます")
        url = reverse("washoku:comment_react", args=[answer.pk])

        self.client.force_login(self.me)
        self.client.post(url, {"kind": "thanks"})
        self.client.post(url, {"kind": "like"})

        self.assertEqual(CommentReaction.objects.count(), 2)
        self.assertEqual(
            sorted(Notification.objects.filter(recipient=self.child, kind="stamp").values_list("stamp", flat=True)),
            ["like", "thanks"],
        )

        page = self.client.get(reverse("washoku:recipe_detail", args=[self.recipe.pk]))
        self.assertContains(page, "🙏 ありがとう <b>1</b>")

        # もう一度押すと取り消し (通知も消える)
        self.client.post(url, {"kind": "like"})
        self.assertEqual(CommentReaction.objects.count(), 1)
        self.assertEqual(Notification.objects.filter(recipient=self.child).count(), 1)

        # 自分のコメントには押せない
        self.client.force_login(self.child)
        self.client.post(url, {"kind": "like"})
        self.assertEqual(CommentReaction.objects.count(), 1)
        self.assertContains(self.client.get(reverse("washoku:notification_list")), "「ありがとう」を押しました")

    def test_new_stamps_on_comments_and_columns(self):

        answer = Comment.objects.create(author=self.child, recipe=self.recipe, kind="tip", body="白ワインで代用できます")

        self.client.force_login(self.me)
        self.client.post(reverse("washoku:comment_react", args=[answer.pk]), {"kind": "genius"})
        self.client.post(reverse("washoku:comment_react", args=[answer.pk]), {"kind": "unknown"})

        self.assertEqual(list(CommentReaction.objects.values_list("kind", flat=True)), ["genius"])
        self.assertContains(self.client.get(reverse("washoku:recipe_detail", args=[self.recipe.pk])), "🤩 天才 <b>1</b>")

        column = Post.objects.create(author=self.child, kind="column", title="Rahm の選び方", body="本文", status="published")
        url = reverse("washoku:post_react", args=[column.pk])

        self.client.post(url, {"kind": "insight"})
        self.client.post(url, {"kind": "check"})
        self.client.post(url, {"kind": "check"})

        self.assertEqual(list(PostReaction.objects.values_list("kind", flat=True)), ["insight"])
        self.assertEqual(
            sorted(Notification.objects.filter(recipient=self.child).values_list("stamp", flat=True)),
            ["genius", "insight"],
        )
        self.assertContains(self.client.get(reverse("washoku:post_detail", args=[column.pk])), "💡 なるほど <b>1</b>")

        # 自分のコラムには押せず、数だけ見える
        self.client.force_login(self.child)
        self.client.post(url, {"kind": "like"})
        self.assertEqual(PostReaction.objects.count(), 1)
        page = self.client.get(reverse("washoku:post_detail", args=[column.pk]))
        self.assertContains(page, "💡 なるほど 1")
        self.assertNotContains(page, "スタンプを押す")
        self.assertContains(self.client.get(reverse("washoku:notification_list")), "「なるほど」を押しました: コラム「Rahm の選び方」")

    def test_stamps_edited_in_admin(self):

        from .models import Stamp

        answer = Comment.objects.create(author=self.child, recipe=self.recipe, kind="tip", body="白ワインで代用できます")
        detail = reverse("washoku:recipe_detail", args=[self.recipe.pk])
        url = reverse("washoku:comment_react", args=[answer.pk])

        Stamp.objects.create(key="onigiri", emoji="🍙", label="おにぎり食べたい", order=1)
        Stamp.objects.filter(key="like").update(label="いいね！")

        self.client.force_login(self.me)
        self.client.post(url, {"kind": "onigiri"})
        self.client.post(url, {"kind": "like"})
        page = self.client.get(detail)
        self.assertContains(page, "🍙 おにぎり食べたい <b>1</b>")
        self.assertContains(page, "👍 いいね！ <b>1</b>")

        # 非表示: 選ぶ欄から消え、新しく押せないが、押されたぶんは残り取り消せる
        Stamp.objects.filter(key__in=["onigiri", "lol"]).update(is_active=False)
        self.client.post(url, {"kind": "lol"})
        self.assertFalse(CommentReaction.objects.filter(kind="lol").exists())
        page = self.client.get(detail)
        self.assertContains(page, "🍙 おにぎり食べたい <b>1</b>")
        self.assertNotContains(page, "😂 笑った")
        self.client.post(url, {"kind": "onigiri"})
        self.assertFalse(CommentReaction.objects.filter(kind="onigiri").exists())
        self.assertNotContains(self.client.get(detail), "おにぎり食べたい")

        self.client.force_login(self.child)
        self.assertContains(self.client.get(reverse("washoku:notification_list")), "「いいね！」を押しました")

    def test_filter_recipes_by_nutrition(self):

        url = reverse("washoku:recipe_list")

        high_protein = self.client.get(url + "?n=protein")
        self.assertContains(high_protein, "照り焼きチキン")
        self.assertNotContains(high_protein, "肉じゃが</h3>")

        low_salt = self.client.get(url + "?n=lowsalt&n=light")
        self.assertContains(low_salt, "肉じゃが")
        self.assertNotContains(low_salt, "照り焼きチキン</h3>")


class CompactPageTests(TestCase):

    def test_tab_pages_skip_the_visible_heading_and_long_lead(self):

        response = self.client.get(reverse("washoku:ingredient_list"))
        self.assertNotContains(response, "何と呼ばれ、どこで買えるか")
        self.assertContains(response, '<h1 class="washoku-visually-hidden">食材と買い方</h1>', html=True)

        response = self.client.get(reverse("washoku:substitute_list"))
        self.assertContains(response, "日本の野菜や食材の代わりに使えるものの紹介です。")

    def test_store_kinds_have_short_labels_and_back_to_top(self):

        response = self.client.get(reverse("washoku:store_list"))

        for label in ("日韓食材店", "中華食材店", "アジア食材店"):
            self.assertContains(response, label)

        self.assertContains(response, "washoku-quick-fit")
        self.assertContains(response, 'aria-label="ページの上へ"')


class QuestionListTests(TestCase):

    def test_open_questions_first_then_answered_ones(self):

        User = get_user_model()
        asker = User.objects.create_user("asker", password="x")
        helper = User.objects.create_user("helper", password="x")
        ingredient = Ingredient.objects.create(name="大根")

        open_question = Comment.objects.create(ingredient=ingredient, author=asker, kind="question", body="どこで買えますか？")
        solved = Comment.objects.create(ingredient=ingredient, author=asker, kind="question", body="Rettich で合っていますか？")
        Comment.objects.create(ingredient=ingredient, author=helper, kind="tip", body="合っています", parent=solved)

        html = self.client.get(reverse("washoku:question_list")).content.decode()

        self.assertLess(html.index("答えを待っている質問"), html.index(open_question.body))
        self.assertLess(html.index(open_question.body), html.index("答えが出た質問"))
        self.assertLess(html.index("答えが出た質問"), html.index(solved.body))
        self.assertIn("返信 1件", html)


class WelcomeAndJoinTests(TestCase):

    def test_logged_out_visitors_are_invited_to_sign_up(self):

        recipe = make_recipe()

        home = self.client.get(reverse("washoku:home"))
        self.assertContains(home, "無料の会員登録でできること")
        self.assertContains(home, reverse("portal:signup"))
        self.assertContains(home, 'id="washoku-welcome"')

        detail = self.client.get(reverse("washoku:recipe_detail", args=[recipe.pk]))
        self.assertContains(detail, "コメントや質問は、")
        self.assertContains(detail, "♡</span> お気に入り")

    def test_members_see_push_hint_instead_of_sign_up(self):

        user = get_user_model().objects.create_user("hanako", password="x")
        self.client.force_login(user)

        home = self.client.get(reverse("washoku:home"))
        self.assertNotContains(home, "無料の会員登録でできること")
        self.assertContains(home, "マイページでオンにする")
        self.assertContains(self.client.get(reverse("washoku:my_page")), "ホーム画面に追加する方法")


class AskAnywhereTests(TestCase):
    """「私からも一言」ボタンと、どこからでも書ける質問のページ"""

    def setUp(self):
        User = get_user_model()
        self.member = User.objects.create_user("hanako", password="x")
        self.editor = User.objects.create_user("henshu", password="x", is_staff=True)
        self.ingredient = Ingredient.objects.create(name="みりん", category="seasoning")

    def test_say_button_points_to_the_current_page(self):

        home = self.client.get(reverse("washoku:home"))
        self.assertContains(home, "私からも<br>一言")
        self.assertContains(home, f'href="{reverse("washoku:question_new")}"')
        self.assertContains(home, "書くには無料の会員登録が必要です")
        self.assertContains(home, f'href="{reverse("washoku:recipe_submit")}"')
        self.assertNotContains(home, "washoku-banner")

        detail_url = reverse("washoku:ingredient_detail", args=[self.ingredient.pk])
        detail = self.client.get(detail_url)
        self.assertContains(detail, f'href="{detail_url}?ask=1#comments"')
        self.assertContains(detail, f'{reverse("washoku:post_submit", args=["product"])}?ingredient={self.ingredient.pk}')

        # 「質問する」から来たときは、最初から質問を選んでおく
        self.client.force_login(self.member)
        asked = self.client.get(detail_url + "?ask=1")
        self.assertContains(asked, 'value="question" checked')
        self.assertNotContains(self.client.get(reverse("washoku:question_new")), "私からも<br>一言")

    def test_question_about_anything_or_an_ingredient(self):

        url = reverse("washoku:question_new")
        self.assertEqual(self.client.get(url).status_code, 302)

        self.client.force_login(self.member)
        page = self.client.get(url + f"?ingredient={self.ingredient.pk}")
        self.assertContains(page, f'value="ingredient:{self.ingredient.pk}" selected')

        self.client.post(url, {"about": "board", "kind": "question", "body": "スイスで日本の包丁を研いでもらえる所は？"})
        board_question = Comment.objects.get()
        self.assertEqual(board_question.kind, "question")
        self.assertEqual(board_question.post.kind, "board")

        Comment.objects.update(created_at=timezone.now() - timedelta(minutes=5))
        self.client.post(url, {"about": f"ingredient:{self.ingredient.pk}", "kind": "question", "body": "本みりんはどこで買えますか？"})
        self.assertEqual(Comment.objects.get(ingredient=self.ingredient).kind, "question")

        questions = self.client.get(reverse("washoku:question_list"))
        self.assertContains(questions, "スイスで日本の包丁")
        self.assertContains(questions, "なんでも質問")
        self.assertContains(self.client.get(board_question.get_absolute_url()), "みんなの質問")

        # 「なんでも質問」の箱そのものは、新着や検索には出さない
        self.assertNotContains(self.client.get(reverse("washoku:activity")), ">なんでも質問</span>")
        self.assertNotContains(self.client.get(reverse("washoku:search") + "?q=なんでも"), "食材やレシピに限らず")

    def test_editor_questions_are_marked_on_home(self):

        Comment.objects.create(author=self.editor, ingredient=self.ingredient, kind="question", body="みりんの代わりに何を使っていますか？")

        home = self.client.get(reverse("washoku:home"))
        self.assertContains(home, "編集部より")
        for label in ["アンケート", "質問", "口コミ", "コラム", "新着"]:
            self.assertContains(home, f">{label}</button>")


class WeeklyTabTests(TestCase):
    """HOMEの「注目」タブ: 編集部のひとこと・一押し、先週のアンケートの結果 (自動)"""

    def test_week_tab_shows_picks_message_and_last_weeks_poll(self):

        from washoku.views import poll_week_start

        column = Post.objects.create(kind="column", title="冬の鍋はこれ", body="白菜はMigrosで。", status="published")
        poll = Post.objects.create(kind="poll", title="お米はどこで買う？", status="published")
        Post.objects.filter(pk=poll.pk).update(created_at=poll_week_start() - timedelta(days=1))
        rice = PollChoice.objects.create(post=poll, label="アジア食材店", order=0)
        PollChoice.objects.create(post=poll, label="Migros", order=1)
        PollVote.objects.create(post=poll, choice=rice, voter_key="a")

        home = self.client.get(reverse("washoku:home"))
        self.assertContains(home, "注目</button>")
        self.assertContains(home, "先週のアンケートの結果")
        self.assertContains(home, "👑 アジア食材店")
        # 先週のアンケートは、HOMEでは投票できない (結果とアンケートのページへのリンクだけ)
        self.assertIsNone(home.context["main_poll"])
        self.assertContains(home, "まだ投票できます")

        column.is_featured = True
        column.save()
        display = DisplaySettings.load()
        display.weekly_message = "今週は鍋の特集です"
        display.save()

        home = self.client.get(reverse("washoku:home"))
        self.assertContains(home, "冬の鍋はこれ")
        self.assertContains(home, "今週は鍋の特集です")

    def test_neutral_review(self):

        post = Post.objects.create(kind="product", title="Coop の味噌", verdict="ok", body="ふつうの味噌です。", status="published")
        reviews = self.client.get(reverse("washoku:product_list") + "?verdict=ok")
        self.assertContains(reviews, "😐 ふつう")
        self.assertContains(reviews, post.title)


class PhotoTests(TestCase):

    def setUp(self):
        User = get_user_model()
        self.member = User.objects.create_user("hanako", password="x")
        self.recipe = make_recipe()

    def photo(self):
        return SimpleUploadedFile("tofu.jpg", b"fake", content_type="image/jpeg")

    def test_comment_with_one_photo_and_delete_removes_it(self):

        self.client.force_login(self.member)
        url = reverse("washoku:comment_create", args=["recipe", self.recipe.pk])

        with mock.patch("washoku.views.upload_photo", return_value="https://res.cloudinary.com/demo/image/upload/v1/yapp/washoku/comments/a.webp") as upload:
            self.client.post(url, {"kind": "tip", "body": "絹ごしはこれが近い", "photo": self.photo()})

        upload.assert_called_once()
        comment = Comment.objects.get()
        self.assertTrue(comment.photo_url.endswith("a.webp"))
        self.assertContains(self.client.get(reverse("washoku:recipe_detail", args=[self.recipe.pk])), comment.photo_url)

        with mock.patch("washoku.views.delete_uploaded_photos") as delete:
            self.client.post(reverse("washoku:comment_delete", args=[comment.pk]))

        delete.assert_called_once_with(comment.photo_url)
        self.assertFalse(Comment.objects.exists())

    def test_photo_that_cannot_be_read_stops_the_comment(self):

        self.client.force_login(self.member)
        url = reverse("washoku:comment_create", args=["recipe", self.recipe.pk])

        with mock.patch("washoku.views.upload_photo", side_effect=ValidationError("画像を正常に読み込めませんでした。")):
            response = self.client.post(url, {"kind": "tip", "body": "写真つき", "photo": self.photo()}, follow=True)

        self.assertContains(response, "画像を正常に読み込めませんでした。")
        self.assertFalse(Comment.objects.exists())
        # 書いた文はフォームに残る (1回だけ)
        self.assertContains(response, "写真つき</textarea>")
        self.assertNotContains(self.client.get(reverse("washoku:recipe_detail", args=[self.recipe.pk])), "写真つき</textarea>")

    def test_failed_reply_keeps_the_draft_in_the_reply_form(self):

        asker = get_user_model().objects.create_user("jiro", password="x")
        question = Comment.objects.create(author=asker, recipe=self.recipe, kind="question", body="どこで買える？")
        self.client.force_login(self.member)
        url = reverse("washoku:comment_create", args=["recipe", self.recipe.pk])

        with mock.patch("washoku.views.upload_photo", side_effect=ValidationError("画像は5MB以下にしてください。")):
            response = self.client.post(url, {"kind": "tip", "parent": question.pk, "body": "Coop にあります", "photo": self.photo()}, follow=True)

        self.assertContains(response, "Coop にあります</textarea>")
        self.assertContains(response, "書いた文はそのまま残してあります。")

    def test_column_takes_two_photos_and_products_none(self):

        self.client.force_login(self.member)

        uploaded = iter(["https://example.com/1.webp", "https://example.com/2.webp"])

        with mock.patch("washoku.views.upload_photo", side_effect=lambda *args: next(uploaded)), \
                mock.patch("washoku.views.send_admin_alert"):
            self.client.post(
                reverse("washoku:post_submit", args=["column"]),
                {"title": "豆腐の選び方", "body": "Coop の Tofu nature は木綿に近いです。", "photo_1": self.photo(), "photo_2": self.photo()},
            )

        post = Post.objects.get()
        self.assertEqual(post.photos(), ["https://example.com/1.webp", "https://example.com/2.webp"])

        page = self.client.get(reverse("washoku:post_submit", args=["product"]))
        self.assertNotContains(page, 'name="photo_1"')
        self.assertContains(self.client.get(reverse("washoku:post_submit", args=["column"])), 'name="photo_2"')

    def test_ingredient_photo_on_substitute_list_and_detail(self):

        kohlrabi = Ingredient.objects.create(
            name="コールラビ", name_de="Kohlrabi", category="vegetable",
            photo_url="https://upload.wikimedia.org/k.jpg", photo_credit="Someone / CC BY-SA 4.0 / Wikimedia Commons",
        )
        Substitute.objects.create(original_name="かぶ", substitute=kohlrabi)

        self.assertContains(self.client.get(reverse("washoku:substitute_list")), "https://upload.wikimedia.org/k.jpg")
        self.assertContains(self.client.get(reverse("washoku:ingredient_detail", args=[kohlrabi.pk])), "CC BY-SA 4.0")

    def test_find_commons_photo_takes_the_first_usable_image_with_credit(self):

        from washoku.photos import commons_query, find_commons_photo, thumbnail_url

        self.assertEqual(commons_query(Ingredient(name="かぶ（テスト）", name_de="Weisse Rüben / Mairübli")), "Weisse Rüben")
        self.assertEqual(commons_query(Ingredient(name="白かぶ", name_de="Weisse Rüben")), "white turnips Brassica rapa")
        self.assertEqual(
            thumbnail_url("https://res.cloudinary.com/demo/image/upload/v1/a.webp", 160),
            "https://res.cloudinary.com/demo/image/upload/c_fill,w_160,h_160/v1/a.webp",
        )

        pages = {
            "1": {"index": 1, "imageinfo": [{"mime": "image/svg+xml", "width": 800}]},
            "2": {"index": 2, "imageinfo": [{
                "mime": "image/jpeg", "width": 1200, "thumburl": "https://upload.wikimedia.org/thumb/k.jpg",
                "descriptionurl": "https://commons.wikimedia.org/wiki/File:K.jpg",
                "extmetadata": {"Artist": {"value": "<a href='x'>Rainer</a>"}, "LicenseShortName": {"value": "CC BY-SA 3.0"}},
            }]},
        }

        response = mock.Mock()
        response.json.return_value = {"query": {"pages": pages}}

        with mock.patch("washoku.photos.requests.get", return_value=response):
            photo = find_commons_photo("Kohlrabi")

        self.assertEqual(photo["url"], "https://upload.wikimedia.org/thumb/k.jpg")
        self.assertEqual(photo["credit"], "Rainer / CC BY-SA 3.0 / Wikimedia Commons")

    def test_members_post_photos_first_is_shown_and_staff_picks_the_rest(self):

        staff = get_user_model().objects.create_user("admin", password="x", is_staff=True)
        other = get_user_model().objects.create_user("yuki", password="x")
        add_url = reverse("washoku:photo_add", args=["recipe", self.recipe.pk])
        page_url = reverse("washoku:recipe_detail", args=[self.recipe.pk])

        # ログインしていない人には投稿の欄が出ない
        self.assertNotContains(self.client.get(page_url), "写真を投稿")

        # 最初の1枚はそのまま載る
        self.client.force_login(self.member)
        self.assertContains(self.client.get(page_url), "写真を投稿")

        with mock.patch("washoku.views.upload_photo", return_value="https://example.com/1.webp"):
            self.client.post(add_url, {"photo": self.photo()})

        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.photo_1, "https://example.com/1.webp")
        self.assertContains(self.client.get(page_url), "写真: hanako さん")

        # 2枚目は候補になり、管理者に知らせる
        self.client.force_login(other)

        with mock.patch("washoku.views.upload_photo", return_value="https://example.com/2.webp"), \
                mock.patch("washoku.views.send_admin_alert") as alert:
            self.client.post(add_url, {"photo": self.photo()})

        alert.assert_called_once()
        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.photo_1, "https://example.com/1.webp")
        second = MemberPhoto.objects.get(url="https://example.com/2.webp")

        # 会員は載せる写真を選べず、ほかの人の写真も消せない
        first = MemberPhoto.objects.get(url="https://example.com/1.webp")
        manage = lambda photo: reverse("washoku:photo_manage", args=[photo.pk])
        self.assertEqual(self.client.post(manage(second), {"action": "show"}).status_code, 404)
        self.assertEqual(self.client.post(manage(first), {"action": "delete"}).status_code, 404)

        # 管理者は2枚目を載せられる
        self.client.force_login(staff)
        self.assertContains(self.client.get(page_url), "これを載せる")
        self.client.post(manage(second), {"action": "show"})
        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.photo_1, "https://example.com/2.webp")

        # 載っている写真を消すと、残りの一番古い写真が載る
        with mock.patch("washoku.views.delete_uploaded_photos") as delete:
            self.client.post(manage(second), {"action": "delete"})

        delete.assert_called_once_with("https://example.com/2.webp")
        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.photo_1, "https://example.com/1.webp")

        # 投稿した本人は自分の写真を消せる
        self.client.force_login(self.member)

        with mock.patch("washoku.views.delete_uploaded_photos"):
            self.client.post(manage(first), {"action": "delete"})

        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.photo_1, "")
        self.assertFalse(MemberPhoto.objects.exists())

    def test_ingredient_photo_and_staff_only_store_photo(self):

        kohlrabi = Ingredient.objects.create(name="コールラビ", name_de="Kohlrabi", category="vegetable", photo_url="https://upload.wikimedia.org/k.jpg", photo_credit="A / CC BY")
        self.client.force_login(self.member)

        with mock.patch("washoku.views.upload_photo", return_value="https://example.com/k.webp"), \
                mock.patch("washoku.views.send_admin_alert"):
            self.client.post(reverse("washoku:photo_add", args=["ingredient", kohlrabi.pk]), {"photo": self.photo()})

        # Wikimedia の写真が載っているので、候補として残る
        kohlrabi.refresh_from_db()
        self.assertEqual(kohlrabi.photo_url, "https://upload.wikimedia.org/k.jpg")
        self.assertEqual(kohlrabi.member_photos.count(), 1)

        store = Store.objects.create(name="Yoshi", kind="japanese", city="Zürich", address="x")
        store_url = reverse("washoku:staff_photo", args=["store", store.pk])
        self.assertEqual(self.client.post(store_url, {"photo": self.photo()}).status_code, 404)

        staff = get_user_model().objects.create_user("admin", password="x", is_staff=True)
        self.client.force_login(staff)

        with mock.patch("washoku.views.upload_photo", return_value="https://example.com/s.webp"):
            self.client.post(store_url, {"photo": self.photo()})

        self.assertContains(self.client.get(reverse("washoku:store_detail", args=[store.pk])), "https://example.com/s.webp")

    def test_recipe_submission_takes_two_photos(self):

        self.client.force_login(self.member)

        uploaded = iter(["https://example.com/a.webp", "https://example.com/b.webp"])

        with mock.patch("washoku.views.upload_photo", side_effect=lambda *args: next(uploaded)), \
                mock.patch("washoku.views.send_admin_alert"):
            self.client.post(reverse("washoku:recipe_submit"), {
                "name": "豆腐ハンバーグ", "category": "meat", "ingredients_text": "鶏もも肉 200g\n木綿豆腐 1丁",
                "steps": "混ぜて焼く", "photo_1": self.photo(), "photo_2": self.photo(),
            })

        recipe = Recipe.objects.get(name="豆腐ハンバーグ")
        self.assertEqual(recipe.photo_1, "https://example.com/a.webp")
        self.assertEqual(list(recipe.member_photos.values_list("url", flat=True)), ["https://example.com/a.webp", "https://example.com/b.webp"])


class PollTests(TestCase):

    def setUp(self):

        self.member = get_user_model().objects.create_user("hanako", password="x")
        self.other = get_user_model().objects.create_user("jiro", password="x")
        self.potato = Ingredient.objects.create(name="テスト用じゃがいも", category="vegetable")

        self.poll = Post.objects.create(kind="poll", title="何色の袋を買う？", status="published")
        self.poll.ingredients.add(self.potato)
        self.green = PollChoice.objects.create(post=self.poll, label="緑", order=0)
        self.red = PollChoice.objects.create(post=self.poll, label="赤", order=1)

    def vote(self, choice, user=None, **extra):
        self.client.force_login(user or self.member)
        return self.client.post(
            reverse("washoku:poll_vote", args=[self.poll.pk]),
            {"choice": choice.pk, **extra},
        )

    def test_first_polls_are_seeded(self):

        import importlib

        from django.apps import apps

        egg = Ingredient.objects.create(name="卵", category="other")
        importlib.import_module("washoku.migrations.0028_first_polls").add_first_polls(apps, None)

        titles = list(Post.objects.filter(kind="poll").exclude(pk=self.poll.pk).values_list("title", flat=True))
        self.assertEqual(list(egg.posts.values_list("title", flat=True)), ["ぶっちゃけ、スイスで生卵を食べたことある？"])

        self.assertIn("ぶっちゃけ、スイスで生卵を食べたことある？", titles)
        self.assertIn("じゃがいもは、いつも何色の袋を買っている？", titles)

    def test_guests_vote_once_per_browser_without_login(self):

        self.vote(self.green)
        self.client.logout()

        # 結果は投票したあとにだけ見える
        page = self.client.get(reverse("washoku:post_detail", args=[self.poll.pk]))
        self.assertNotContains(page, "100%")
        self.assertContains(page, "ログイン不要！投票すると結果が見られる")
        self.assertContains(page, 'name="choice"')

        # ログインしていない人も投票でき、同じブラウザなら選び直しになる
        self.client.post(reverse("washoku:poll_vote", args=[self.poll.pk]), {"choice": self.red.pk})
        self.client.post(reverse("washoku:poll_vote", args=[self.poll.pk]), {"choice": self.green.pk})
        self.assertEqual(PollVote.objects.count(), 2)
        guest_vote = PollVote.objects.get(user__isnull=True)
        self.assertEqual(guest_vote.choice, self.green)
        self.assertTrue(guest_vote.voter_key)

        page = self.client.get(reverse("washoku:post_detail", args=[self.poll.pk]))
        self.assertContains(page, "✓ 緑")
        self.assertContains(page, "2人が回答")

        # 別のブラウザ (cookie なし) は別の1票
        self.client.cookies.clear()
        self.client.post(reverse("washoku:poll_vote", args=[self.poll.pk]), {"choice": self.red.pk})
        self.assertEqual(PollVote.objects.filter(user__isnull=True).count(), 2)

    def test_one_vote_per_member_and_it_can_be_changed(self):

        self.vote(self.green)
        self.vote(self.red)
        self.vote(self.red, user=self.other)

        self.assertEqual(PollVote.objects.filter(post=self.poll).count(), 2)
        self.assertEqual(PollVote.objects.get(user=self.member).choice, self.red)

        page = self.client.get(reverse("washoku:post_detail", args=[self.poll.pk]))
        self.assertContains(page, "✓ 赤")
        self.assertContains(page, "2人が回答")

    def test_home_shows_newest_unanswered_poll_including_free_text(self):

        text_poll = Post.objects.create(kind="poll", title="恋しい日本の味は？", status="published", poll_type="text")

        # 新しい自由記述のアンケートが大きく出る
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(reverse("washoku:home")).context["main_poll"], text_poll)

        # 答えたら、まだ答えていないアンケートへ
        self.client.post(reverse("washoku:poll_vote", args=[text_poll.pk]), {"answer": "おでん"})
        self.assertEqual(self.client.get(reverse("washoku:home")).context["main_poll"], self.poll)

        # 全部答えたら、いちばん新しいもの
        self.vote(self.green)
        self.assertEqual(self.client.get(reverse("washoku:home")).context["main_poll"], text_poll)

    def test_multiple_choice_poll_keeps_every_ticked_choice(self):

        self.poll.poll_type = "multiple"
        self.poll.save()
        url = reverse("washoku:poll_vote", args=[self.poll.pk])

        self.client.force_login(self.member)
        self.client.post(url, {"choice": [self.green.pk, self.red.pk]})
        self.assertEqual(PollVote.objects.filter(user=self.member).count(), 2)

        # 選び直すと、外したものは消える
        self.client.post(url, {"choice": [self.red.pk]})
        self.assertEqual(list(PollVote.objects.filter(user=self.member).values_list("choice", flat=True)), [self.red.pk])

        self.client.force_login(self.other)
        self.client.post(url, {"choice": [self.green.pk, self.red.pk]})

        page = self.client.get(reverse("washoku:post_detail", args=[self.poll.pk]))
        self.assertContains(page, 'type="checkbox"')
        self.assertContains(page, "2人が回答")
        self.assertContains(page, "100%")

    def test_free_text_poll_shows_answers_after_answering(self):

        from .models import PollAnswer

        self.poll.poll_type = "text"
        self.poll.save()
        url = reverse("washoku:poll_vote", args=[self.poll.pk])

        self.client.force_login(self.other)
        self.client.post(url, {"answer": "Coop の緑の袋"})

        self.client.force_login(self.member)
        page = self.client.get(reverse("washoku:post_detail", args=[self.poll.pk]))
        self.assertContains(page, 'name="answer"')
        self.assertNotContains(page, "Coop の緑の袋")

        self.client.post(url, {"answer": "Migros の赤"})
        self.client.post(url, {"answer": "Migros の赤い袋"})
        self.assertEqual(PollAnswer.objects.get(user=self.member).text, "Migros の赤い袋")

        hidden = PollAnswer.objects.get(user=self.other)
        page = self.client.get(reverse("washoku:post_detail", args=[self.poll.pk]))
        self.assertContains(page, "Coop の緑の袋")
        self.assertContains(page, "2件の答え")

        hidden.is_hidden = True
        hidden.save()
        self.assertNotContains(self.client.get(reverse("washoku:post_detail", args=[self.poll.pk])), "Coop の緑の袋")

        # ログインしていない人も答えられる
        self.client.logout()
        self.client.post(url, {"answer": "見ないで買う"})
        self.assertEqual(PollAnswer.objects.filter(user__isnull=True).count(), 1)

    def test_vote_needs_a_choice_of_this_published_poll(self):

        other_poll = Post.objects.create(kind="poll", title="別の", status="published")
        other_choice = PollChoice.objects.create(post=other_poll, label="はい")

        self.assertEqual(self.vote(other_choice).status_code, 404)

        self.poll.status = "draft"
        self.poll.save()
        self.assertEqual(self.vote(self.green).status_code, 404)
        self.assertFalse(PollVote.objects.exists())

    def test_vote_returns_to_the_page_it_came_from(self):

        page = reverse("washoku:ingredient_detail", args=[self.potato.pk])

        self.assertRedirects(
            self.vote(self.green, next=page),
            f"{page}#poll-{self.poll.pk}",
            fetch_redirect_response=False,
        )
        self.assertRedirects(
            self.vote(self.green, next="https://example.com/"),
            reverse("washoku:post_detail", args=[self.poll.pk]) + f"#poll-{self.poll.pk}",
            fetch_redirect_response=False,
        )

    def test_ingredient_page_shows_the_poll_to_vote_in_place(self):

        self.client.force_login(self.member)
        page = self.client.get(reverse("washoku:ingredient_detail", args=[self.potato.pk]))

        self.assertContains(page, f'id="poll-{self.poll.pk}"')
        self.assertContains(page, 'name="choice"')
        self.assertEqual(page.context["related_posts"], [])

    def test_poll_list_and_members_cannot_create_polls(self):

        self.vote(self.green)

        page = self.client.get(reverse("washoku:poll_list"))
        self.assertContains(page, "何色の袋を買う？")
        self.assertContains(page, "1票")
        self.assertNotContains(page, "アンケートを作る")

        self.assertEqual(self.client.get(reverse("washoku:post_submit", args=["poll"])).status_code, 404)


class FeaturedTests(TestCase):

    def test_home_features_columns_and_comments_with_recent_stamps(self):

        User = get_user_model()
        author, fan, fan2 = (User.objects.create_user(name, password="x") for name in ("a", "b", "c"))
        ingredient = Ingredient.objects.create(name="テスト食材", category="other")

        column = Post.objects.create(kind="column", title="人気のコラム", body="本文です。", status="published", author=author)
        quiet = Post.objects.create(kind="column", title="静かなコラム", body="本文です。", status="published", author=author)
        comment = Comment.objects.create(ingredient=ingredient, author=author, body="人気のコメント")
        old = Comment.objects.create(ingredient=ingredient, author=author, body="昔のコメント")

        PostReaction.objects.create(post=column, user=fan, kind="thanks")
        PostReaction.objects.create(post=column, user=fan2, kind="thanks")
        CommentReaction.objects.create(comment=comment, user=fan, kind="thanks")
        CommentReaction.objects.filter(
            pk=CommentReaction.objects.create(comment=old, user=fan, kind="thanks").pk
        ).update(created_at=timezone.now() - timedelta(days=60))

        home = self.client.get(reverse("washoku:home"))

        self.assertEqual(
            [(entry["item"].pk, entry["count"]) for entry in home.context["featured"]],
            [(column.pk, 2), (comment.pk, 1)],
        )
        self.assertContains(home, "washoku-week-picks")
        # 種類 (コラムなど) と投稿者、コメントは投稿した場所 (食材の名前) を出す
        self.assertContains(home, '<span class="washoku-week-kind">コラム</span>')
        self.assertContains(home, f"{author.username} ・ {ingredient.name}")


class ColumnOrderTests(TestCase):

    def test_column_list_is_newest_first_even_with_counts(self):

        now = timezone.now()
        old = Post.objects.create(kind="column", title="古いコラム", body="本文です。", status="published", created_at=now - timedelta(days=3))
        new = Post.objects.create(kind="column", title="新しいコラム", body="本文です。", status="published", created_at=now)

        page = self.client.get(reverse("washoku:column_list"))

        self.assertEqual([post.pk for post in page.context["posts"]], [new.pk, old.pk])


class AdminPickTests(TestCase):

    def setUp(self):
        User = get_user_model()
        self.author = User.objects.create_user("a", password="x")
        self.other = User.objects.create_user("b", password="x")
        self.ingredient = Ingredient.objects.create(name="テスト食材", category="other")

    def test_picked_items_come_first_in_featured(self):

        popular = Post.objects.create(kind="column", title="人気", body="本文です。", status="published", author=self.author)
        PostReaction.objects.create(post=popular, user=self.other, kind="thanks")
        picked = Comment.objects.create(ingredient=self.ingredient, author=self.author, body="選んだコメント", is_featured=True)
        Post.objects.create(kind="column", title="下書き", body="本文です。", status="draft", is_featured=True)

        featured = self.client.get(reverse("washoku:home")).context["featured"]

        self.assertEqual([(entry["item"].pk, entry["count"]) for entry in featured], [(picked.pk, None), (popular.pk, 1)])

        # スタンプ数は表示設定でオンにしたときだけ出す
        self.assertNotContains(self.client.get(reverse("washoku:home")), "😊1")
        DisplaySettings.objects.update_or_create(pk=1, defaults={"home_featured_show_stamps": True})
        self.assertContains(self.client.get(reverse("washoku:home")), "😊1")

    def test_reopened_question_stays_open_with_a_reply(self):

        question = Comment.objects.create(ingredient=self.ingredient, author=self.author, kind="question", body="どこで買える？")
        Comment.objects.create(ingredient=self.ingredient, author=self.other, parent=question, body="確認します")

        # 解決済みは2日間「解決済」付きで残る
        questions = self.client.get(reverse("washoku:home")).context["questions"]
        self.assertEqual([(q.pk, q.has_answer) for q in questions], [(question.pk, True)])

        question.reopened = True
        question.save()

        self.assertEqual([q.pk for q in self.client.get(reverse("washoku:home")).context["questions"]], [question.pk])

    def test_reopen_ticked_on_the_reply_reopens_the_question(self):

        question = Comment.objects.create(ingredient=self.ingredient, author=self.author, kind="question", body="どこで買える？")
        Comment.objects.create(ingredient=self.ingredient, author=self.other, parent=question, body="確認します", reopened=True)

        self.assertEqual([q.pk for q in self.client.get(reverse("washoku:home")).context["questions"]], [question.pk])

    def test_solved_questions_stay_on_home_for_two_days(self):

        from datetime import timedelta
        from django.utils import timezone

        open_q = Comment.objects.create(ingredient=self.ingredient, author=self.author, kind="question", body="未解決の質問")
        solved = Comment.objects.create(ingredient=self.ingredient, author=self.author, kind="question", body="解決した質問")
        reply = Comment.objects.create(ingredient=self.ingredient, author=self.other, parent=solved, body="Coop にあります")

        home = self.client.get(reverse("washoku:home"))
        self.assertEqual([q.pk for q in home.context["questions"]], [open_q.pk, solved.pk])
        self.assertContains(home, "解決済")
        self.assertContains(home, 'class="is-solved"')

        # 管理者が写真を足したときだけ、カードに写真が出る
        self.assertNotContains(home, "https://example.com/q.jpg")
        Comment.objects.filter(pk=open_q.pk).update(home_photo_url="https://example.com/q.jpg")
        home = self.client.get(reverse("washoku:home"))
        self.assertContains(home, '<img src="https://example.com/q.jpg"')
        self.assertContains(home, "data-home-tabs")
        self.assertContains(home, "答えを募集中")
        # 注目と同じく、投稿者と投稿した場所を出す
        self.assertContains(home, f"{open_q.author.username} ・ {self.ingredient.name}")

        # 3日たつと消える (未解決はずっと残る)
        Comment.objects.filter(pk=reply.pk).update(created_at=timezone.now() - timedelta(days=3))
        self.assertEqual([q.pk for q in self.client.get(reverse("washoku:home")).context["questions"]], [open_q.pk])

        # 管理画面で期限を延ばせる / HOMEから外せる
        Comment.objects.filter(pk=solved.pk).update(home_until=timezone.now() + timedelta(days=1))
        Comment.objects.filter(pk=open_q.pk).update(home_hidden=True)
        self.assertEqual([q.pk for q in self.client.get(reverse("washoku:home")).context["questions"]], [solved.pk])

    def test_featured_order_and_hidden(self):

        link = Post.objects.create(kind="link", title="参考リンク", url="https://example.com", status="published", is_featured=True, featured_order=2)
        first = Comment.objects.create(ingredient=self.ingredient, author=self.author, body="いちばん上", is_featured=True, featured_order=1)
        popular = Post.objects.create(kind="column", title="人気", body="本文です。", status="published", author=self.author)
        PostReaction.objects.create(post=popular, user=self.other, kind="thanks")

        featured = self.client.get(reverse("washoku:home")).context["featured"]
        self.assertEqual([entry["item"].pk for entry in featured], [first.pk, link.pk, popular.pk])

        # 自動で入ったものも、管理画面で外せる
        popular.featured_hidden = True
        popular.save()
        featured = self.client.get(reverse("washoku:home")).context["featured"]
        self.assertEqual([entry["item"].pk for entry in featured], [first.pk, link.pk])

        staff = get_user_model().objects.create_superuser("admin", password="x")
        self.client.force_login(staff)
        page = self.client.get(reverse("admin:washoku_post_changelist"))
        self.assertContains(page, 'name="form-0-featured_order"')


class PhotoReplaceTests(TestCase):

    def setUp(self):
        User = get_user_model()
        self.member = User.objects.create_user("hanako", password="x")
        self.other = User.objects.create_user("jiro", password="x")
        self.recipe = make_recipe()

    def photo(self):
        return SimpleUploadedFile("tofu.jpg", b"fake", content_type="image/jpeg")

    def test_member_replaces_own_shown_photo_and_admin_is_told(self):

        self.client.force_login(self.member)

        with mock.patch("washoku.views.upload_photo", return_value="https://example.com/a.webp"), \
                mock.patch("washoku.views.send_admin_alert") as alert:
            self.client.post(reverse("washoku:photo_add", args=["recipe", self.recipe.pk]), {"photo": self.photo()})

        alert.assert_called_once()
        photo = MemberPhoto.objects.get()
        self.assertFalse(photo.admin_checked)

        with mock.patch("washoku.views.upload_photo", return_value="https://example.com/b.webp"), \
                mock.patch("washoku.views.delete_uploaded_photos") as delete, \
                mock.patch("washoku.views.send_admin_alert") as alert:
            self.client.post(reverse("washoku:photo_manage", args=[photo.pk]), {"action": "replace", "photo": self.photo()})

        alert.assert_called_once()
        delete.assert_called_once_with("https://example.com/a.webp")
        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.photo_1, "https://example.com/b.webp")

        # ほかの人は差し替えられない
        self.client.force_login(self.other)
        with mock.patch("washoku.views.upload_photo", return_value="https://example.com/c.webp"):
            response = self.client.post(reverse("washoku:photo_manage", args=[photo.pk]), {"action": "replace", "photo": self.photo()})
        self.assertEqual(response.status_code, 404)

    def test_author_replaces_and_removes_column_photo(self):

        post = Post.objects.create(author=self.member, kind="column", title="豆腐", body="本文です。", status="published", photo_1="https://example.com/1.webp")
        url = reverse("washoku:post_photo", args=[post.pk])

        self.client.force_login(self.member)
        self.assertContains(self.client.get(reverse("washoku:post_detail", args=[post.pk])), "写真を変える・消す")

        with mock.patch("washoku.views.upload_photo", return_value="https://example.com/2.webp"), \
                mock.patch("washoku.views.delete_uploaded_photos"), \
                mock.patch("washoku.views.send_admin_alert") as alert:
            self.client.post(url, {"field": "photo_1", "photo": self.photo()})
            self.client.post(url, {"field": "photo_2", "photo": self.photo()})
            self.client.post(url, {"field": "photo_1", "remove": "1"})

        self.assertEqual(alert.call_count, 2)
        post.refresh_from_db()
        self.assertEqual(post.photos(), ["https://example.com/2.webp"])

        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url, {"field": "photo_2", "remove": "1"}).status_code, 404)
        self.assertNotContains(self.client.get(reverse("washoku:post_detail", args=[post.pk])), "写真を変える・消す")


class PollCommentsOnIngredientTests(TestCase):

    def test_poll_comments_show_under_ingredient_poll(self):

        User = get_user_model()
        member = User.objects.create_user("hanako", password="x")
        potato = Ingredient.objects.create(name="じゃがいも", category="vegetable")
        poll = Post.objects.create(kind="poll", title="何色の袋？", status="published")
        poll.ingredients.add(potato)
        PollChoice.objects.create(post=poll, label="緑", order=1)
        Comment.objects.create(post=poll, author=member, body="いつも緑です")

        page = self.client.get(reverse("washoku:ingredient_detail", args=[potato.pk]))
        self.assertContains(page, "washoku-poll-inline")
        self.assertContains(page, "いつも緑です")
        self.assertContains(page, "コメント1件を見る・書く")


class ColumnPollTests(TestCase):

    def test_column_with_choices_shows_a_poll_at_the_end(self):

        User = get_user_model()
        member = User.objects.create_user("hanako", password="x")
        column = Post.objects.create(kind="column", title="Rahm の選び方", body="本文です。", status="published", poll_question="どの Rahm を使う？")
        plain = Post.objects.create(kind="column", title="ふつうのコラム", body="本文です。", status="published")
        vollrahm = PollChoice.objects.create(post=column, label="Vollrahm", order=1)
        PollChoice.objects.create(post=column, label="Halbrahm", order=2)

        page = self.client.get(reverse("washoku:post_detail", args=[column.pk]))
        self.assertContains(page, "どの Rahm を使う？")
        self.assertContains(page, "Halbrahm")
        self.assertNotContains(self.client.get(reverse("washoku:post_detail", args=[plain.pk])), "washoku-poll-rows")

        self.client.force_login(member)
        self.client.post(reverse("washoku:poll_vote", args=[column.pk]), {"choice": vollrahm.pk})
        self.assertEqual(PollVote.objects.get().choice, vollrahm)
        self.assertContains(self.client.get(reverse("washoku:post_detail", args=[column.pk])), "100%")

        # HOME の大きいアンケート欄にも、新しいアンケートとして出る
        home = self.client.get(reverse("washoku:home"))
        self.assertEqual(home.context["main_poll"].pk, column.pk)

        # アンケート一覧にも、コラムのアンケートとして出る (アンケートのないコラムは出ない)
        polls = self.client.get(reverse("washoku:poll_list"))
        self.assertContains(polls, "どの Rahm を使う？")
        self.assertContains(polls, "コラム「Rahm の選び方」より")
        self.assertContains(polls, f"#poll-{column.pk}")
        self.assertNotContains(polls, "ふつうのコラム")
        self.assertContains(home, f"/washoku/posts/{column.pk}/#poll-{column.pk}")



class PollVoteAdminTests(TestCase):

    def test_admin_sees_who_answered_what(self):

        User = get_user_model()
        staff = User.objects.create_superuser("boss", password="x")
        member = User.objects.create_user("hanako", password="x")
        poll = Post.objects.create(kind="poll", title="何色の袋？", status="published")
        green = PollChoice.objects.create(post=poll, label="緑", order=1)
        PollVote.objects.create(post=poll, choice=green, user=member)

        self.client.force_login(staff)
        self.assertContains(self.client.get(reverse("admin:washoku_post_change", args=[poll.pk])), "hanako")
        page = self.client.get(reverse("admin:washoku_pollvote_changelist"))
        self.assertContains(page, "hanako")
        self.assertContains(page, "緑")


class ColumnListDisplayTests(TestCase):

    def test_column_list_shows_author_time_stamps_and_follows_settings(self):

        User = get_user_model()
        author = User.objects.create_user("hanako", password="x")
        fan = User.objects.create_user("taro", password="x")
        column = Post.objects.create(kind="column", title="薄切り肉のコツ", body="本文", author=author, status="published")
        PostReaction.objects.create(post=column, user=fan, kind="insight")
        PostReaction.objects.create(post=column, user=author, kind="like")
        time_text = timezone.localtime(column.created_at).strftime("%H:%M")

        page = self.client.get(reverse("washoku:column_list"))
        self.assertContains(page, "hanako")
        self.assertContains(page, time_text)
        self.assertNotContains(page, "😊 2")  # スタンプ数は最初は出さない

        settings_row = DisplaySettings.load()
        settings_row.column_show_stamps = True
        settings_row.save()
        self.assertContains(self.client.get(reverse("washoku:column_list")), "😊 2")

        settings_row.column_show_author = False
        settings_row.column_show_time = False
        settings_row.column_show_stamps = False
        settings_row.save()

        page = self.client.get(reverse("washoku:column_list"))
        self.assertNotContains(page, "hanako")
        self.assertNotContains(page, time_text)
        self.assertNotContains(page, "😊 2")

    def test_admin_opens_the_single_settings_page(self):

        User = get_user_model()
        self.client.force_login(User.objects.create_superuser("boss", password="x"))
        response = self.client.get(reverse("admin:washoku_displaysettings_changelist"))
        self.assertRedirects(response, reverse("admin:washoku_displaysettings_change", args=[1]))

    def test_columns_sort_by_newest_or_most_readers(self):

        import uuid

        from usage_analytics.models import PageView

        older = Post.objects.create(kind="column", title="古いけど人気", body="x", status="published")
        newer = Post.objects.create(kind="column", title="新しいコラム", body="x", status="published")
        Post.objects.filter(pk=older.pk).update(created_at=timezone.now() - timedelta(days=3))
        for _ in range(2):
            PageView.objects.create(visitor_id=uuid.uuid4(), visit_id=uuid.uuid4(), app_key="washoku", path=f"/washoku/posts/{older.pk}/")
        PageView.objects.create(visitor_id=uuid.uuid4(), visit_id=uuid.uuid4(), app_key="washoku", path=f"/washoku/posts/{newer.pk}/photo/")

        titles = lambda response: [post.title for post in response.context["posts"]]

        self.assertEqual(titles(self.client.get(reverse("washoku:column_list"))), ["新しいコラム", "古いけど人気"])

        # 切り替えは最初は出さず、人気順を指定しても新着順のまま
        hidden = self.client.get(reverse("washoku:column_list"), {"sort": "popular"})
        self.assertEqual(titles(hidden), ["新しいコラム", "古いけど人気"])
        self.assertNotContains(hidden, "washoku-sort-switch")

        DisplaySettings.objects.filter(pk=DisplaySettings.load().pk).update(column_show_sort=True)
        popular = self.client.get(reverse("washoku:column_list"), {"sort": "popular"})
        self.assertContains(popular, "washoku-sort-switch")
        self.assertEqual(titles(popular), ["古いけど人気", "新しいコラム"])
        self.assertEqual([post.reader_count for post in popular.context["posts"]], [2, 0])


class PollSuggestionTests(TestCase):

    def test_guest_suggests_and_admin_makes_a_draft_poll(self):

        url = reverse("washoku:poll_suggest")
        self.assertEqual(self.client.get(url).status_code, 200)

        with mock.patch("washoku.views.send_admin_alert") as alert:
            response = self.client.post(url, {"question": "納豆はどこで買っている？", "choices": "アジア食材店\n\nネット通販\n自分で作る", "note": ""})

        self.assertRedirects(response, f"{url}?sent=1")
        alert.assert_called_once()
        suggestion = PollSuggestion.objects.get()
        self.assertIsNone(suggestion.user)
        self.assertEqual(suggestion.choice_lines(), ["アジア食材店", "ネット通販", "自分で作る"])

        # ボット (隠し項目あり) は保存しない
        session = self.client.session
        session["washoku_poll_suggest_sent_at"] = 0
        session.save()
        self.client.post(url, {"question": "spam", "choices": "", "website": "http://spam"})
        self.assertEqual(PollSuggestion.objects.count(), 1)

        User = get_user_model()
        boss = User.objects.create_superuser("boss", password="x")
        self.client.force_login(boss)
        self.client.post(
            reverse("admin:washoku_pollsuggestion_changelist"),
            {"action": "make_draft_polls", "_selected_action": [suggestion.pk]},
        )

        suggestion.refresh_from_db()
        self.assertEqual(suggestion.status, "adopted")
        self.assertEqual(suggestion.poll.status, "draft")
        self.assertEqual(suggestion.poll.kind, "poll")
        self.assertEqual(list(suggestion.poll.choices.values_list("label", flat=True)), ["アジア食材店", "ネット通販", "自分で作る"])


class HomePollTests(TestCase):

    def test_home_shows_the_newest_poll_not_yet_answered(self):

        older = Post.objects.create(kind="poll", title="古いアンケート", status="published")
        older_choice = PollChoice.objects.create(post=older, label="はい", order=1)
        newer = Post.objects.create(kind="poll", title="新しいアンケート", status="published")
        newer_choice = PollChoice.objects.create(post=newer, label="いいえ", order=1)

        home = self.client.get(reverse("washoku:home"))
        self.assertEqual(home.context["main_poll"].pk, newer.pk)
        self.assertEqual([poll.pk for poll in home.context["other_polls"]], [older.pk])
        self.assertContains(home, "聞いてみたいことを提案する")

        # 新しいほうに答えた直後はその結果を見せ、次に開いたときは、まだ答えていない古いほうが大きく出る
        response = self.client.post(reverse("washoku:poll_vote", args=[newer.pk]), {"choice": newer_choice.pk, "next": "/washoku/"})
        self.assertRedirects(response, f"/washoku/?poll={newer.pk}#poll-{newer.pk}", fetch_redirect_response=False)
        self.assertEqual(self.client.get(f"/washoku/?poll={newer.pk}").context["main_poll"].pk, newer.pk)
        self.assertEqual(self.client.get(reverse("washoku:home")).context["main_poll"].pk, older.pk)

        # 全部答えたら、いちばん新しいもの
        self.client.post(reverse("washoku:poll_vote", args=[older.pk]), {"choice": older_choice.pk, "next": "/washoku/"})
        self.assertEqual(self.client.get(reverse("washoku:home")).context["main_poll"].pk, newer.pk)
