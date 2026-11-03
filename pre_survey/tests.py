from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from travel.models import UserProfile

from .models import Answer, FeatureWish, Interest, Participant, Question, Skip
from .services import current_consent, suggest_username


User = get_user_model()

PASSWORD = "Swiss-Ask-2026!"


def make_question(body, theme="life", **extra):
    return Question.objects.create(body=body, theme=theme, **extra)


class FlowMixin:

    def join(self, client=None, themes=("life",), region="", mode="custom", name="さくら", wish="already"):
        client = client or self.client
        client.post(reverse("pre_survey:start"), {"agree": "yes"})
        client.post(reverse("pre_survey:nickname"), {"mode": mode, "custom_name": name, "auto_name": "森のリス"})
        client.post(reverse("pre_survey:themes"), {"themes": list(themes), "region": region})
        if wish:
            # 「0問目」(掲示板に求める機能) を済ませる
            client.post(reverse("pre_survey:wish"), {"action": wish})
        return Participant.objects.filter(pk=client.session["pre_survey_participant"]).first()

    def current(self, client=None):
        return (client or self.client).get(reverse("pre_survey:question")).context["question"]

    def act(self, question, action, body="知っています", client=None):
        return (client or self.client).post(
            reverse("pre_survey:question_action", args=[question.pk]),
            {"action": action, "body": body},
        )


class ParticipationTests(FlowMixin, TestCase):

    def test_start_page_shows_consent_and_login(self):
        response = self.client.get(reverse("pre_survey:start"))
        self.assertContains(response, "回答の公開について")
        self.assertContains(response, "ログインする")
        self.assertNotContains(response, "※ 文面を変えるときは")

    def test_must_agree(self):
        self.client.post(reverse("pre_survey:start"), {})
        self.assertFalse(Participant.objects.exists())

    def test_consent_version_and_time_are_recorded(self):
        participant = self.join()
        self.assertEqual(participant.consent_version, current_consent()[0])
        self.assertIsNotNone(participant.consented_at)

    def test_steps_cannot_be_skipped(self):
        response = self.client.get(reverse("pre_survey:question"))
        self.assertRedirects(response, reverse("pre_survey:start"))

    def test_nickname_modes(self):
        self.assertEqual(self.join(name="ゆき").nickname, "ゆき")
        self.assertEqual(self.join(mode="auto").nickname, "森のリス")
        participant = self.join(mode="anonymous")
        self.assertEqual(participant.nickname, "")
        self.assertEqual(participant.display_name, "名無しさん")

    def test_custom_nickname_required(self):
        self.client.post(reverse("pre_survey:start"), {"agree": "yes"})
        response = self.client.post(reverse("pre_survey:nickname"), {"mode": "custom", "custom_name": " "})
        self.assertContains(response, "ニックネームを入力してください")

    def test_answer_is_saved_with_browser_token_and_nickname(self):
        question = make_question("Q1")
        participant = self.join()
        self.act(question, "answer", "Coop で買えます")
        answer = Answer.objects.get()
        self.assertEqual(answer.body, "Coop で買えます")
        self.assertEqual(answer.nickname, "さくら")
        self.assertEqual(answer.browser_token, participant.browser_token)
        self.assertIsNone(answer.user)
        self.assertTrue(answer.publish_consent)

    def test_double_submit_saves_one_answer(self):
        question = make_question("Q1")
        self.join()
        self.act(question, "answer")
        self.act(question, "answer")
        self.assertEqual(Answer.objects.count(), 1)

    def test_answer_length_limit(self):
        question = make_question("Q1")
        self.join()
        self.act(question, "answer", "あ" * 1001)
        self.assertFalse(Answer.objects.exists())

    def test_finish_button_after_three_answers(self):
        questions = [make_question(f"Q{i}") for i in range(5)]
        self.join()
        for question in questions[:2]:
            self.act(question, "answer")
        self.assertFalse(self.client.get(reverse("pre_survey:question")).context["can_finish"])
        self.act(questions[2], "answer")
        response = self.client.get(reverse("pre_survey:question"))
        self.assertTrue(response.context["can_finish"])
        self.assertContains(response, "ここで終了")

    def test_interest_is_recorded_and_moves_on(self):
        question = make_question("Q1")
        other = make_question("Q2")
        self.join()
        response = self.client.get(reverse("pre_survey:question"))
        self.assertEqual(response.context["question"], other)
        self.assertContains(response, "ほかの方の意見を聞いてみたい質問には「私も知りたい」をどうぞ")
        self.act(other, "interest")
        self.assertEqual(Interest.objects.get().question, other)
        self.assertEqual(self.current(), question)

    def test_skip_can_be_undone(self):
        question = make_question("Q1")
        self.join()
        self.act(question, "skip")
        self.assertIsNone(self.current())
        response = self.client.post(reverse("pre_survey:undo_skip", args=[question.pk]))
        self.assertFalse(Skip.objects.exists())
        self.assertEqual(self.client.get(response.url).context["question"], question)

    def test_ask_questions_up_to_five(self):
        self.join()
        for number in range(6):
            self.client.post(reverse("pre_survey:ask"), {"theme": "work", "body": f"質問{number}"})
        self.assertEqual(Question.objects.filter(source="member").count(), 5)
        question = Question.objects.filter(source="member").first()
        self.assertEqual(question.status, Question.Status.PUBLISHED)
        self.assertEqual(question.nickname, "さくら")

    def test_finish_goes_through_ask_step(self):
        questions = [make_question(f"Q{i}") for i in range(3)]
        self.join()
        for question in questions:
            self.act(question, "answer")
        response = self.client.get(reverse("pre_survey:question"))
        self.assertContains(response, reverse("pre_survey:ask") + "?last=1")
        response = self.client.get(reverse("pre_survey:ask") + "?last=1")
        self.assertContains(response, "最後に、知りたいことはありますか？")
        self.assertContains(response, "質問せずに終了する")
        response = self.client.post(reverse("pre_survey:ask"), {"theme": "life", "body": "質問", "last": "1"})
        self.assertRedirects(response, reverse("pre_survey:ask") + "?last=1")

    def test_done_page_offers_asking_until_limit(self):
        self.join()
        self.assertContains(self.client.get(reverse("pre_survey:done")), "知りたいことを質問する")
        for number in range(5):
            self.client.post(reverse("pre_survey:ask"), {"theme": "life", "body": f"質問{number}"})
        self.assertNotContains(self.client.get(reverse("pre_survey:done")), "知りたいことを質問する")

    def test_ask_only_without_answering(self):
        self.client.post(reverse("pre_survey:start"), {"agree": "yes"})
        self.client.post(reverse("pre_survey:nickname"), {"mode": "anonymous"})
        response = self.client.post(reverse("pre_survey:themes"), {"themes": ["life"], "next": "ask"})
        self.assertRedirects(response, reverse("pre_survey:wish") + "?next=ask")
        response = self.client.post(reverse("pre_survey:wish"), {"action": "skip", "next": "ask"})
        self.assertRedirects(response, reverse("pre_survey:ask"))

    def test_again_keeps_nickname_and_previous_themes(self):
        first = self.join(themes=("life", "work"), region="zurich")
        self.client.get(reverse("pre_survey:done"))
        response = self.client.post(reverse("pre_survey:again"))
        self.assertRedirects(response, reverse("pre_survey:question"), fetch_redirect_response=False)
        response = self.client.get(reverse("pre_survey:themes"))
        checked = [option["value"] for option in response.context["theme_options"] if option["checked"]]
        self.assertEqual(checked, ["life", "work"])
        second = Participant.objects.exclude(pk=first.pk).get()
        self.assertEqual(second.nickname, "さくら")
        self.assertEqual(second.region, "zurich")
        self.assertEqual(second.browser_token, first.browser_token)

    def test_themes_page_has_select_all_and_zurich_by_default(self):
        self.client.post(reverse("pre_survey:start"), {"agree": "yes"})
        self.client.post(reverse("pre_survey:nickname"), {"mode": "anonymous"})
        response = self.client.get(reverse("pre_survey:themes"))
        self.assertContains(response, "すべて選択")
        self.assertContains(response, "いつでもスキップできます")
        self.assertEqual(response.context["region"], "zurich")
        self.assertNotIn("other", [option["value"] for option in response.context["theme_options"]])

    def test_again_keeps_no_region_if_chosen(self):
        self.join(region="")
        self.client.post(reverse("pre_survey:again"))
        self.assertEqual(self.client.get(reverse("pre_survey:themes")).context["region"], "")

    def test_finish_box_at_top_after_three_answers(self):
        questions = [make_question(f"Q{i}") for i in range(4)]
        self.join()
        for question in questions[:3]:
            self.act(question, "answer")
        response = self.client.get(reverse("pre_survey:question"))
        content = response.content.decode()
        self.assertIn("ここで回答を終えて、あなたが聞きたいことを教えていただくこともできます", content)
        self.assertLess(content.index("回答を終えて、聞きたいことを書く"), content.index("ps-question-body"))

    def test_ask_with_other_theme(self):
        self.join(themes=("life",))
        response = self.client.get(reverse("pre_survey:ask"))
        self.assertContains(response, "その他")
        self.client.post(reverse("pre_survey:ask"), {"theme": "other", "body": "どのテーマでもない質問"})
        asked = Question.objects.get(source="member")
        self.assertEqual(asked.theme, "other")
        other = self.client_class()
        self.join(client=other, themes=("life",))
        self.assertEqual(self.current(other), asked)

    def test_region_choices_start_with_zurich(self):
        self.client.post(reverse("pre_survey:start"), {"agree": "yes"})
        self.client.post(reverse("pre_survey:nickname"), {"mode": "anonymous"})
        response = self.client.get(reverse("pre_survey:themes"))
        self.assertEqual(response.context["regions"][0][0], "zurich")


class FeatureWishTests(FlowMixin, TestCase):

    def test_wish_comes_before_the_first_question(self):
        make_question("Q1")
        self.join(wish=None)
        response = self.client.get(reverse("pre_survey:question"))
        self.assertRedirects(response, reverse("pre_survey:wish") + "?next=question")
        response = self.client.get(response.url)
        self.assertContains(response, "こんな機能があったら使ってみたい！と思うものは？")
        self.assertContains(response, "前に回答しました")

    def test_themes_go_to_wish_first(self):
        self.client.post(reverse("pre_survey:start"), {"agree": "yes"})
        self.client.post(reverse("pre_survey:nickname"), {"mode": "anonymous"})
        response = self.client.post(reverse("pre_survey:themes"), {"themes": ["life"], "next": "ask"})
        self.assertRedirects(response, reverse("pre_survey:wish") + "?next=ask")

    def test_answer_is_saved_and_not_asked_again(self):
        question = make_question("Q1")
        self.join(wish=None)
        response = self.client.post(reverse("pre_survey:wish"), {
            "action": "answer",
            "features": ["qa", "giveaway", "other", "bogus"],
            "other_text": "ベビーシッター探し",
            "comment": "地域で分けてほしい",
            "next": "question",
        })
        self.assertRedirects(response, reverse("pre_survey:question"))
        wish = FeatureWish.objects.get()
        self.assertEqual(wish.features, ["qa", "giveaway", "other"])
        self.assertEqual(wish.other_text, "ベビーシッター探し")
        self.assertEqual(wish.comment, "地域で分けてほしい")
        self.assertEqual(wish.response, FeatureWish.Response.ANSWERED)
        self.assertEqual(self.current(), question)

        self.client.post(reverse("pre_survey:again"))
        self.assertEqual(self.client.get(reverse("pre_survey:question")).status_code, 200)

    def test_empty_answer_asks_to_choose_or_skip(self):
        self.join(wish=None)
        response = self.client.post(reverse("pre_survey:wish"), {"action": "answer"})
        self.assertContains(response, "あてはまるものを選ぶか")
        self.assertFalse(FeatureWish.objects.exists())

    def test_skip_shows_it_once_more_next_time_but_already_does_not(self):
        self.join(wish="skip")
        self.assertEqual(self.client.get(reverse("pre_survey:question")).status_code, 200)
        self.client.post(reverse("pre_survey:again"))
        self.assertRedirects(self.client.get(reverse("pre_survey:question")), reverse("pre_survey:wish") + "?next=question")
        self.client.post(reverse("pre_survey:wish"), {"action": "already"})
        self.client.post(reverse("pre_survey:again"))
        self.assertEqual(self.client.get(reverse("pre_survey:question")).status_code, 200)

    def test_admin_tally_and_csv(self):
        admin_user = User.objects.create_superuser("boss", password=PASSWORD)
        FeatureWish.objects.create(features=["qa", "events"])
        FeatureWish.objects.create(features=["qa"])
        FeatureWish.objects.create(response=FeatureWish.Response.SKIPPED)
        self.client.force_login(admin_user)
        response = self.client.get(reverse("admin:pre_survey_featurewish_changelist"))
        self.assertContains(response, "回答 2件・スキップ 1件")
        self.assertEqual(response.context["wish_tally"][0]["count"], 2)
        response = self.client.post(
            reverse("admin:pre_survey_featurewish_changelist"),
            {"action": "export_csv", "_selected_action": list(FeatureWish.objects.values_list("pk", flat=True))},
        )
        self.assertIn("困ったことを質問・相談できる（知恵袋）", response.content.decode("utf-8-sig"))


class DeliveryTests(FlowMixin, TestCase):

    def test_only_published_questions(self):
        make_question("hidden", status=Question.Status.HIDDEN)
        make_question("rejected", status=Question.Status.REJECTED)
        make_question("pending", status=Question.Status.PENDING)
        wanted = make_question("life")
        self.join(themes=("life",))
        self.assertEqual(self.current(), wanted)
        self.act(wanted, "answer")
        self.assertIsNone(self.current())

    def test_chosen_themes_first_then_other_themes(self):
        work = make_question("work", theme="work")
        life = make_question("life")
        self.join(themes=("life",))
        self.assertEqual(self.current(), life)
        self.act(life, "answer")
        response = self.client.get(reverse("pre_survey:question"))
        self.assertEqual(response.context["question"], work)
        self.assertContains(response, "ほかのテーマの質問もお出ししています")

    def test_questions_answered_by_others_are_still_asked(self):
        question = make_question("Q1")
        for _ in range(3):
            Answer.objects.create(question=question, body="ほかの人の回答")
        self.join()
        self.assertEqual(self.current(), question)

    def test_own_question_is_not_asked_back(self):
        self.join(themes=("life",))
        self.client.post(reverse("pre_survey:ask"), {"theme": "life", "body": "自分の質問"})
        self.assertIsNone(self.current())

    def test_fewest_answers_first_then_newest(self):
        busy = make_question("busy")
        quiet = make_question("quiet")
        newest_empty = make_question("newest empty")
        older_empty = make_question("older empty")
        Question.objects.filter(pk=older_empty.pk).update(created_at=busy.created_at.replace(year=2020))
        for _ in range(2):
            Answer.objects.create(question=busy, body="x")
        Answer.objects.create(question=quiet, body="x")
        # 非表示の回答は数えない
        Answer.objects.create(question=newest_empty, body="x", is_hidden=True)

        self.join()
        order = []
        while (question := self.current()) is not None:
            order.append(question.body)
            self.act(question, "answer")
        self.assertEqual(order, ["newest empty", "older empty", "quiet", "busy"])

    def test_answered_questions_never_come_back(self):
        question = make_question("Q1")
        self.join()
        self.act(question, "answer")
        self.client.post(reverse("pre_survey:again"))
        self.client.post(reverse("pre_survey:themes"), {"themes": ["life"]})
        self.assertIsNone(self.current())

    def test_skipped_question_comes_back_last_next_time(self):
        skipped = make_question("skipped")
        other = make_question("other")
        self.join()
        self.act(self.current(), "skip")  # other (newest)
        self.assertEqual(self.current(), skipped)
        self.act(skipped, "skip")
        self.assertIsNone(self.current())

        self.client.post(reverse("pre_survey:again"))
        self.client.post(reverse("pre_survey:themes"), {"themes": ["life"]})
        fresh = make_question("fresh")
        self.assertEqual(self.current(), fresh)
        self.act(fresh, "answer")
        self.assertIn(self.current(), [skipped, other])

    def test_regional_questions(self):
        zurich = make_question("zurich", region="zurich")
        make_question("geneva", region="geneva")
        everywhere = make_question("everywhere")
        self.join(region="zurich")
        seen = []
        while (question := self.current()) is not None:
            seen.append(question)
            self.act(question, "answer")
        self.assertCountEqual(seen, [zurich, everywhere])

    def test_member_question_reaches_another_respondent(self):
        self.join(themes=("shopping",))
        self.client.post(reverse("pre_survey:ask"), {"theme": "shopping", "body": "納豆はどこで買えますか？"})
        asked = Question.objects.get(source="member")

        # 別の人に、承認 (公開) 済みの質問として届く
        other = self.client_class()
        self.join(client=other, themes=("shopping",), name="ゆき")
        self.assertEqual(self.current(other), asked)
        self.act(asked, "answer", "Migros にあります", client=other)
        self.assertEqual(asked.answers.get().body, "Migros にあります")

    def test_hidden_member_question_is_not_delivered(self):
        self.join(themes=("shopping",))
        self.client.post(reverse("pre_survey:ask"), {"theme": "shopping", "body": "変な質問"})
        Question.objects.filter(source="member").update(status=Question.Status.HIDDEN)
        other = self.client_class()
        self.join(client=other, themes=("shopping",))
        self.assertIsNone(self.current(other))


class AccountTests(FlowMixin, TestCase):

    def make_public_user(self, username="hana", **extra):
        user = User.objects.create_user(username, password=PASSWORD, **extra)
        user.groups.add(Group.objects.get_or_create(name="public_users")[0])
        UserProfile.objects.update_or_create(
            user=user,
            defaults={"nickname": "はな", "password_setup_completed": True, "nickname_setup_completed": True},
        )
        return user

    def test_logged_in_public_user_can_take_part(self):
        user = self.make_public_user()
        self.client.force_login(user)
        response = self.client.get(reverse("pre_survey:nickname"))
        self.assertRedirects(response, reverse("pre_survey:start"))
        self.client.post(reverse("pre_survey:start"), {"agree": "yes"})
        response = self.client.get(reverse("pre_survey:nickname"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["custom_name"], "はな")

        question = make_question("Q1")
        self.client.post(reverse("pre_survey:nickname"), {"mode": "custom", "custom_name": "はな"})
        self.client.post(reverse("pre_survey:themes"), {"themes": ["life"]})
        self.act(question, "answer")
        self.assertEqual(Answer.objects.get().user, user)
        response = self.client.get(reverse("pre_survey:done"))
        self.assertNotIn("signup_form", response.context)

    def test_login_midway_links_this_participation(self):
        user = self.make_public_user()
        question = make_question("Q1")
        participant = self.join()
        self.act(question, "answer")
        self.client.force_login(user)
        self.client.get(reverse("pre_survey:question"))
        participant.refresh_from_db()
        self.assertEqual(participant.user, user)
        self.assertEqual(Answer.objects.get().user, user)

    def test_logged_in_user_does_not_get_own_answered_questions_on_new_browser(self):
        user = self.make_public_user()
        question = make_question("Q1")
        self.client.force_login(user)
        self.join()
        self.act(question, "answer")
        other_browser = self.client_class()
        other_browser.force_login(user)
        self.join(client=other_browser)
        self.assertIsNone(self.current(other_browser))

    def test_signup_from_done_page(self):
        question = make_question("Q1")
        self.join(name="さくら")
        self.act(question, "answer")
        self.client.post(reverse("pre_survey:ask"), {"theme": "life", "body": "質問"})
        response = self.client.get(reverse("pre_survey:done"))
        self.assertEqual(response.context["signup_form"]["username"].value(), "さくら")

        response = self.client.post(
            reverse("pre_survey:done_signup"),
            {"username": "さくら", "password1": PASSWORD, "password2": PASSWORD},
        )
        self.assertRedirects(response, reverse("pre_survey:done"))
        user = User.objects.get(username="さくら")
        self.assertTrue(user.groups.filter(name="public_users").exists())
        self.assertEqual(user.profile.nickname, "さくら")
        self.assertTrue(user.profile.nickname_setup_completed)
        self.assertEqual(Answer.objects.get().user, user)
        self.assertEqual(Question.objects.get(source="member").user, user)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_taken_nickname_gets_another_suggestion(self):
        self.make_public_user(username="さくら")
        self.join(name="さくら")
        response = self.client.get(reverse("pre_survey:done"))
        self.assertEqual(response.context["signup_form"]["username"].value(), "さくら2")
        self.assertTrue(response.context["nickname_taken"])

        response = self.client.post(
            reverse("pre_survey:done_signup"),
            {"username": "さくら", "password1": PASSWORD, "password2": PASSWORD},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["suggested_username"], "さくら2")

    def test_signup_offer_for_every_logged_out_respondent(self):
        self.join(mode="auto")
        response = self.client.get(reverse("pre_survey:done"))
        self.assertEqual(response.context["signup_form"]["username"].value(), "森のリス")
        other = self.client_class()
        self.join(client=other, mode="anonymous")
        response = other.get(reverse("pre_survey:done"))
        self.assertEqual(response.context["signup_form"]["username"].value(), "")
        self.assertContains(response, "ユーザーIDとパスワードを決めるだけで登録できます")

    def test_suggest_username_strips_spaces(self):
        self.assertEqual(suggest_username("さくら テスト"), ("さくらテスト", False))
        self.assertEqual(suggest_username("🌸"), ("", False))


class AdminTests(FlowMixin, TestCase):

    def setUp(self):
        self.admin = User.objects.create_superuser("boss", password=PASSWORD)
        self.client.force_login(self.admin)

    def test_admin_lists_and_sorts(self):
        question = make_question("Q1")
        Answer.objects.create(question=question, body="A1")
        for name in ["question", "answer", "participant"]:
            response = self.client.get(reverse(f"admin:pre_survey_{name}_changelist"))
            self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse("admin:pre_survey_question_changelist") + "?o=7")
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse("admin:pre_survey_question_change", args=[question.pk]))
        self.assertContains(response, "A1")

    def test_status_actions(self):
        question = make_question("Q1")
        self.client.post(
            reverse("admin:pre_survey_question_changelist"),
            {"action": "reject", "_selected_action": [question.pk]},
        )
        question.refresh_from_db()
        self.assertEqual(question.status, Question.Status.REJECTED)

    def test_csv_exports(self):
        question = make_question("納豆はどこ？")
        Answer.objects.create(question=question, body="Migros", nickname="ゆき")
        response = self.client.post(
            reverse("admin:pre_survey_question_changelist"),
            {"action": "export_csv", "_selected_action": [question.pk]},
        )
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("納豆はどこ？", response.content.decode("utf-8-sig"))
        response = self.client.post(
            reverse("admin:pre_survey_answer_changelist"),
            {"action": "export_csv", "_selected_action": [question.answers.get().pk]},
        )
        self.assertIn("Migros", response.content.decode("utf-8-sig"))


class ImportTests(TestCase):

    def test_import_is_idempotent(self):
        call_command("import_pre_survey_questions", verbosity=0)
        count = Question.objects.count()
        self.assertEqual(count, 80)
        self.assertEqual(set(Question.objects.values_list("theme", flat=True)),
                         {"life", "shopping", "childcare", "work", "language", "outing", "health", "money", "culture"})
        Question.objects.filter(seed_key="q01").update(body="直した")
        call_command("import_pre_survey_questions", verbosity=0)
        self.assertEqual(Question.objects.count(), count)
        self.assertEqual(Question.objects.get(seed_key="q01").body, "直した")
        self.assertFalse(Question.objects.exclude(source="staff").exists())


class ActivityPageTests(FlowMixin, TestCase):

    def setUp(self):
        self.admin_user = User.objects.create_superuser("boss", password=PASSWORD)

    def test_shows_everything_in_time_order(self):
        questions = [make_question(f"Q{i}") for i in range(3)]
        participant = self.join(wish=None, name="ゆき")
        self.client.post(reverse("pre_survey:wish"), {"action": "answer", "features": ["qa"]})
        self.act(self.current(), "answer", "Coopで買えます")
        self.act(self.current(), "skip")
        self.act(self.current(), "interest")
        self.client.post(reverse("pre_survey:ask"), {"theme": "life", "body": "自分の質問"})

        staff = self.client_class()
        staff.force_login(self.admin_user)
        response = staff.get(reverse("admin:pre_survey_activity"))
        self.assertEqual(response.status_code, 200)
        kinds = [event["kind"] for event in response.context["events"]]
        self.assertEqual(kinds, ["質問の追加", "私も知りたい", "スキップ", "回答", "0問目: 回答", "参加の開始"])
        self.assertContains(response, "Coopで買えます")
        self.assertEqual(response.context["people"], 1)

        # 人ごと・参加ごとに絞り込める
        by_person = staff.get(reverse("admin:pre_survey_activity") + f"?token={participant.browser_token}")
        self.assertEqual(len(by_person.context["events"]), 6)
        by_participation = staff.get(reverse("admin:pre_survey_activity") + f"?participant={participant.pk}")
        self.assertEqual(len(by_participation.context["events"]), 6)
        self.assertEqual(len(staff.get(reverse("admin:pre_survey_activity") + "?date=2020-01-01").context["events"]), 0)

    def test_records_left_after_a_participation_is_deleted(self):
        make_question("Q1")
        participant = self.join(wish=None)
        self.client.post(reverse("pre_survey:wish"), {"action": "answer", "features": ["qa"]})
        participant.delete()
        staff = self.client_class()
        staff.force_login(self.admin_user)
        response = staff.get(reverse("admin:pre_survey_activity"))
        self.assertContains(response, "参加なし")
        self.assertEqual(response.context["events"][0]["kind"], "0問目: 回答")

    def test_staff_only_and_linked_from_participants(self):
        self.assertEqual(self.client.get(reverse("admin:pre_survey_activity")).status_code, 302)
        staff = self.client_class()
        staff.force_login(self.admin_user)
        self.assertContains(staff.get(reverse("admin:pre_survey_participant_changelist")), reverse("admin:pre_survey_activity"))


class LabelTimeTests(TestCase):

    def test_labels_use_swiss_time(self):
        from datetime import datetime, timezone as dt_timezone

        participant = Participant.objects.create(
            browser_token="d7f13000-0000-4000-8000-000000000000",
            nickname="チーズ好きのヤギ",
            consent_version="v1",
            consented_at=datetime(2026, 11, 3, 15, 42, tzinfo=dt_timezone.utc),
        )
        Participant.objects.filter(pk=participant.pk).update(created_at=datetime(2026, 11, 3, 15, 42, tzinfo=dt_timezone.utc))
        participant.refresh_from_db()
        # 15:42 UTC は冬のスイス時間で 16:42
        self.assertEqual(str(participant), "チーズ好きのヤギ (2026-11-03 16:42)")
