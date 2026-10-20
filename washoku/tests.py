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
    Recipe,
    RecipeIngredient,
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

    def test_bundled_recipes_are_all_approved(self):

        recipes = json.loads((Path(__file__).parent / "data" / "recipes.json").read_text(encoding="utf-8"))

        self.assertEqual({recipe["status"] for recipe in recipes}, {"published"})

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
        self.assertNotContains(self.client.get(reverse("washoku:question_list")), "みりん")

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

        for name in ["my_favorites", "my_comments"]:
            response = self.client.get(reverse(f"washoku:{name}"))
            self.assertEqual(response.status_code, 302, name)

    def test_my_pages_list_favorites_and_comments(self):

        user = get_user_model().objects.create_user("taro", password="x")
        recipe = make_recipe()
        RecipeRating.objects.create(user=user, recipe=recipe, rating=5)
        Comment.objects.create(author=user, recipe=recipe, kind="tip", body="みりんは少なめが好き")

        self.client.force_login(user)

        self.assertEqual(self.client.get(reverse("washoku:my_page")).status_code, 200)
        self.assertContains(self.client.get(reverse("washoku:my_favorites")), recipe.name)
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

    def test_phone_tabbar_ends_with_qa_and_header_links_my_page(self):

        html = self.client.get(reverse("washoku:home")).content.decode()
        tabbar = html[html.index('class="washoku-tabbar"'):]

        self.assertIn(reverse("washoku:question_list"), tabbar)
        self.assertNotIn(reverse("washoku:my_page"), tabbar)
        self.assertIn('class="washoku-me', html)
        self.assertNotIn("家庭料理のレシピ集です", html)
