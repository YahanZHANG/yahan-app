import json
import tempfile

from datetime import timedelta

from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Comment,
    Feedback,
    HouseholdInvite,
    Ingredient,
    MoodTag,
    Notification,
    CommentReaction,
    Post,
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

        for name in ["my_favorites", "family_favorites", "my_notes", "my_comments"]:
            response = self.client.get(reverse(f"washoku:{name}"))
            self.assertEqual(response.status_code, 302, name)

    def test_my_pages_list_favorites_and_comments(self):

        user = get_user_model().objects.create_user("taro", password="x")
        recipe = make_recipe()
        RecipeRating.objects.create(user=user, recipe=recipe, rating=5)
        Comment.objects.create(author=user, recipe=recipe, kind="tip", body="みりんは少なめが好き")

        self.client.force_login(user)

        self.assertEqual(self.client.get(reverse("washoku:my_page")).status_code, 200)
        self.assertContains(self.client.get(reverse("washoku:family_favorites")), recipe.name)
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

    def test_phone_tabbar_ends_with_community_and_header_links_my_page(self):

        html = self.client.get(reverse("washoku:home")).content.decode()
        tabbar = html[html.index('class="washoku-tabbar"'):]

        self.assertIn(reverse("washoku:question_list"), tabbar)
        self.assertNotIn(reverse("washoku:my_page"), tabbar)
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

    def test_hidden_from_search_engines_until_launch(self):

        self.assertContains(self.client.get(self.urls[0]), '<meta name="robots" content="noindex, nofollow">')

        with self.settings(WASHOKU_ALLOW_SEARCH_ENGINES=True):
            self.assertNotContains(self.client.get(self.urls[0]), 'name="robots"')


class NutritionTests(TestCase):

    def test_recipe_shows_nutrition_and_pfc_balance(self):

        recipe = make_recipe(energy_kcal=340, protein_g=28, fat_g=20, carbs_g=12, salt_g=2.6)

        self.assertEqual(recipe.pfc_ratio(), {"protein": 33, "fat": 53, "carbs": 14})

        response = self.client.get(reverse("washoku:recipe_detail", args=[recipe.pk]))

        self.assertContains(response, "1人分の栄養")
        self.assertContains(response, "340<small>kcal</small>")
        self.assertContains(response, "P 33% ・ F 53% ・ C 14%")

    def test_recipe_without_nutrition_hides_the_box(self):

        recipe = make_recipe()

        self.assertIsNone(recipe.pfc_ratio())
        self.assertNotContains(
            self.client.get(reverse("washoku:recipe_detail", args=[recipe.pk])),
            "1人分の栄養",
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
        self.assertContains(response, "washoku-entry-random")
        self.assertContains(response, f'action="{reverse("washoku:search")}"')
        self.assertNotContains(response, "みんなの知恵")

        response = self.client.get(reverse("washoku:recipe_list"))
        self.assertContains(response, "ほかの探し方")
        self.assertContains(response, reverse("washoku:my_favorites"))
        self.assertContains(response, reverse("washoku:family_favorites"))


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

    def test_product_needs_a_shop_and_can_be_filtered(self):

        self.client.force_login(self.member)
        url = reverse("washoku:post_submit", args=["product"])

        response = self.client.post(url, {"title": "冷凍ギョーザ", "body": "日本の味にかなり近いです。"})
        self.assertContains(response, "このフィールドは必須です")

        self.client.post(
            url,
            {"title": "冷凍ギョーザ", "shops": ["migros", "coop"], "section": "frozen", "resembles": "冷凍餃子", "body": "日本の味にかなり近いです。"},
        )
        Post.objects.update(status="published")

        self.assertEqual(Post.objects.get().shop_labels(), ["Migros", "Coop"])

        list_url = reverse("washoku:product_list")
        self.assertContains(self.client.get(list_url + "?shop=migros"), "冷凍ギョーザ")
        self.assertContains(self.client.get(list_url + "?shop=migros"), "冷凍餃子に近い")
        self.assertContains(self.client.get(list_url + "?shop=coop"), "冷凍ギョーザ")
        self.assertNotContains(self.client.get(list_url + "?shop=denner"), "冷凍ギョーザ")
        self.assertNotContains(self.client.get(reverse("washoku:column_list")), "冷凍ギョーザ")

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

        links = self.client.get(reverse("washoku:link_list"))
        self.assertContains(links, "食材探しの記事")
        self.assertNotContains(links, "Coop で買える日本の食材の話です。")
        self.assertNotContains(self.client.get(reverse("washoku:column_list")), "食材探しの記事")

        detail = self.client.get(post.get_absolute_url())
        self.assertContains(detail, 'href="https://example.com/article"')
        self.assertContains(detail, "元の記事を読む")
        self.assertContains(detail, "紹介: hanako さん")

    def test_import_adds_reference_links_once(self):

        get_user_model().objects.create_superuser("owner", password="x")

        for _ in range(2):
            call_command("import_washoku", "--new-only", "--no-geocode", stdout=open("/dev/null", "w"))

        links = Post.objects.filter(kind="link")

        self.assertEqual(links.count(), 5)
        self.assertEqual(links.filter(status="published").count(), 4)
        self.assertEqual(set(links.values_list("author__username", flat=True)), {"owner"})
        self.assertTrue(all(link.source for link in links))


class SubstituteListTests(TestCase):

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

    def test_home_shows_three_latest_comments_and_links_to_all(self):

        for number in range(4):
            Comment.objects.create(author=self.member, recipe=self.recipe, kind="tip", body=f"コメント{number}")

        Post.objects.create(kind="product", title="冷凍餃子", body="x" * 20, shop="migros", status="published")

        home = self.client.get(reverse("washoku:home"))

        self.assertContains(home, "コメント3")
        self.assertNotContains(home, "コメント0")
        self.assertContains(home, reverse("washoku:activity"))

        activity = self.client.get(reverse("washoku:activity"))

        self.assertContains(activity, "コメント0")
        self.assertContains(activity, "冷凍餃子")
        html = activity.content.decode()
        self.assertLess(html.index("冷凍餃子"), html.index("コメント3"))


class AnnouncementTests(TestCase):

    def test_latest_active_announcement_is_shown_on_home(self):

        from .models import Announcement

        self.assertNotContains(self.client.get(reverse("washoku:home")), "washoku-announcement-text")

        Announcement.objects.create(message="古いお知らせ")
        Announcement.objects.create(message="和風洋食を10品追加しました")
        Announcement.objects.create(message="非表示", is_active=False)

        response = self.client.get(reverse("washoku:home"))

        self.assertContains(response, "和風洋食を10品追加しました")
        self.assertNotContains(response, "古いお知らせ")
        self.assertContains(response, "washoku_announcement_closed")

        Announcement.objects.update(created_at=timezone.now() - timedelta(days=30))
        self.assertNotContains(self.client.get(reverse("washoku:home")), "washoku-announcement-text")


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

        html = self.client.get(reverse("washoku:my_favorites") + "?sort=family").content.decode()
        self.assertLess(html.index("肉じゃが"), html.index("照り焼きチキン"))

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
        html = self.client.get(reverse("washoku:family_favorites")).content.decode()

        self.assertIn("家族の好きな料理", html)
        self.assertLess(html.index("肉じゃが"), html.index("照り焼きチキン"))
        self.assertNotIn("other", html)

        self.assertContains(
            self.client.get(reverse("washoku:recipe_detail", args=[self.recipe.pk])),
            "評価は、あなたと家族のメンバーにだけ見えます",
        )

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
        self.assertTrue(Notification.objects.filter(recipient=self.child, kind="thanks").exists())

        page = self.client.get(reverse("washoku:recipe_detail", args=[self.recipe.pk]))
        self.assertContains(page, "🙏 ありがとう <b>1</b>")

        # もう一度押すと取り消し
        self.client.post(url, {"kind": "like"})
        self.assertEqual(CommentReaction.objects.count(), 1)

        # 自分のコメントには押せない
        self.client.force_login(self.child)
        self.client.post(url, {"kind": "like"})
        self.assertEqual(CommentReaction.objects.count(), 1)
        self.assertContains(self.client.get(reverse("washoku:notification_list")), "「ありがとう」を送りました")

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

        for label in ("日韓食材店", "中華食材店", "その他のアジア食材店"):
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
