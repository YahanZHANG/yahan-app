import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from pre_survey.models import Answer as SurveyAnswer
from pre_survey.models import Interest as SurveyInterest
from pre_survey.models import Question as SurveyQuestion

from .models import (
    Answer, BoardSettings, Interest, Item, ItemRequest, Message, Post, PostLike, PostReply, Question, Report, Thanks,
)
from .services import import_from_survey


User = get_user_model()
PASSWORD = "Swiss-Board-2026!"


def public_user(username):
    user = User.objects.create_user(username, password=PASSWORD)
    group, _ = Group.objects.get_or_create(name="public_users")
    user.groups.add(group)
    return user


class BoardTestCase(TestCase):

    def setUp(self):
        settings_row = BoardSettings.current()
        settings_row.is_open = True
        settings_row.save()
        self.alice = public_user("alice")
        self.bob = public_user("bob")


class GateTests(TestCase):

    def test_closed_board_shows_waiting_page_but_staff_see_it(self):
        response = self.client.get(reverse("chiebukuro:home"))
        self.assertContains(response, "いま準備しています")
        staff = User.objects.create_user("staff", password=PASSWORD, is_staff=True)
        self.client.force_login(staff)
        response = self.client.get(reverse("chiebukuro:home"))
        self.assertContains(response, "いまは運営だけが見られます")

    def test_old_board_moved(self):
        self.assertEqual(reverse("swiss_board:home"), "/swiss-board-old/")
        self.assertEqual(reverse("chiebukuro:home"), "/swiss-board/")


class SurveyImportTests(BoardTestCase):

    def make_survey(self):
        staff_q = SurveyQuestion.objects.create(body="おすすめの歯医者は？", theme="health")
        member_q = SurveyQuestion.objects.create(body="お土産は何を買う？", theme="shopping", source="member", nickname="トム")
        SurveyQuestion.objects.create(body="非公開の質問", theme="life", status=SurveyQuestion.Status.HIDDEN)
        SurveyAnswer.objects.create(question=staff_q, body="Smile がいいです", nickname="Yunyun", publish_consent=True)
        SurveyAnswer.objects.create(question=staff_q, body="同意なし", nickname="x", publish_consent=False)
        SurveyAnswer.objects.create(question=staff_q, body="非表示", nickname="y", publish_consent=True, is_hidden=True)
        SurveyAnswer.objects.create(question=member_q, body="チョコレート", nickname="白鳥", publish_consent=True)
        for _ in range(3):
            SurveyInterest.objects.create(question=staff_q, browser_token=uuid.uuid4())
        return staff_q, member_q

    def test_imports_published_questions_and_consented_answers_once(self):
        staff_q, member_q = self.make_survey()
        self.assertEqual(import_from_survey(), (2, 2))
        self.assertEqual(import_from_survey(), (0, 0))

        dentist = Question.objects.get(body="おすすめの歯医者は？")
        self.assertEqual(dentist.source, Question.Source.STAFF)
        self.assertEqual(dentist.survey_interest_count, 3)
        self.assertEqual(list(dentist.answers.values_list("body", "nickname")), [("Smile がいいです", "Yunyun")])
        self.assertIsNotNone(dentist.last_answered_at)
        self.assertEqual(Question.objects.get(body="お土産は何を買う？").display_name, "トム")

        # 新しい答えだけが次に入る
        SurveyAnswer.objects.create(question=member_q, body="塩", nickname="空", publish_consent=True)
        self.assertEqual(import_from_survey(), (0, 1))

    def test_deleted_items_do_not_come_back(self):
        self.make_survey()
        import_from_survey()
        Question.objects.get(body="お土産は何を買う？").delete()
        Answer.objects.filter(body="Smile がいいです").delete()
        self.assertEqual(import_from_survey(), (0, 0))
        self.assertFalse(Question.objects.filter(body="お土産は何を買う？").exists())

    def test_admin_import_button(self):
        self.make_survey()
        admin_user = User.objects.create_superuser("boss", password=PASSWORD)
        self.client.force_login(admin_user)
        response = self.client.post(reverse("admin:chiebukuro_import_survey"), follow=True)
        self.assertContains(response, "質問 2 件・答え 2 件")
        for name in ["boardsettings", "question", "answer", "item", "itemrequest", "report"]:
            self.assertEqual(self.client.get(reverse(f"admin:chiebukuro_{name}_changelist")).status_code, 200)


class QuestionTests(BoardTestCase):

    def test_home_tabs_and_filters(self):
        dentist = Question.objects.create(body="歯医者は？", theme="health", region="zurich")
        best = Answer.objects.create(question=dentist, body="Smile がいいです", nickname="Yunyun")
        Answer.objects.create(question=dentist, body="日本で治す", nickname="空")
        Thanks.objects.create(answer=best, user=self.alice)
        Question.objects.create(body="お土産は？", theme="shopping")
        Question.objects.create(body="ジュネーブの公園は？", theme="outing", region="geneva")

        # 人気: 答えのある質問だけ、いちばん参考になった答えを見せる
        response = self.client.get(reverse("chiebukuro:home"))
        self.assertContains(response, "歯医者は？")
        self.assertContains(response, "Smile がいいです")
        self.assertContains(response, "ほかの答えも見る（全2件）")
        self.assertNotContains(response, "お土産は？")

        # 答え待ち
        response = self.client.get(reverse("chiebukuro:home") + "?tab=waiting")
        self.assertContains(response, "お土産は？")
        self.assertNotContains(response, "歯医者は？")

        # 地域: その地域 + スイス全体
        response = self.client.get(reverse("chiebukuro:home") + "?tab=waiting&region=zurich")
        self.assertContains(response, "お土産は？")
        self.assertNotContains(response, "ジュネーブの公園は？")

        response = self.client.get(reverse("chiebukuro:home") + "?tab=waiting&theme=outing")
        self.assertContains(response, "ジュネーブの公園は？")
        self.assertNotContains(response, "お土産は？")

        # キーワード: 答えの中も探す
        response = self.client.get(reverse("chiebukuro:home") + "?q=Smile")
        self.assertContains(response, "「Smile」の質問 1件")

    def test_new_tab_mixes_posts_questions_answers_items(self):
        question = Question.objects.create(body="新しい質問", theme="life")
        Answer.objects.create(question=question, body="新しい答え", nickname="x")
        Post.objects.create(body="Coop に枝豆がありました", author=self.alice, nickname="alice", theme="shopping")
        Item.objects.create(kind="give", title="ベビーカー", owner=self.bob)
        response = self.client.get(reverse("chiebukuro:home") + "?tab=new")
        for text in ["新しい質問", "新しい答え", "Coop に枝豆がありました", "ベビーカー"]:
            self.assertContains(response, text)
        response = self.client.get(reverse("chiebukuro:home") + "?tab=new&theme=shopping")
        self.assertContains(response, "枝豆")
        self.assertNotContains(response, "新しい質問")

    def test_wanted_questions_first_in_popular(self):
        popular = Question.objects.create(body="人気", theme="life", survey_interest_count=2)
        quiet = Question.objects.create(body="静か", theme="life")
        for question in (popular, quiet):
            Answer.objects.create(question=question, body="A")
        Interest.objects.create(question=quiet, user=self.alice)
        response = self.client.get(reverse("chiebukuro:home"))
        self.assertEqual([q.body for q in response.context["questions"]], ["人気", "静か"])

    def test_best_answer_first_on_question_page(self):
        question = Question.objects.create(body="Q", theme="life")
        Answer.objects.create(question=question, body="最初の答え")
        helpful = Answer.objects.create(question=question, body="役に立つ答え")
        Thanks.objects.create(answer=helpful, user=self.alice)
        response = self.client.get(reverse("chiebukuro:question", args=[question.pk]))
        self.assertEqual(response.context["answers"][0], helpful)
        self.assertContains(response, "いちばん参考になった答え")

    def test_ask_answer_interest_thanks(self):
        self.client.force_login(self.alice)
        response = self.client.post(reverse("chiebukuro:ask"), {"body": "おすすめの小児科は？", "theme": "childcare", "region": "zurich"})
        question = Question.objects.get()
        self.assertRedirects(response, reverse("chiebukuro:question", args=[question.pk]))
        self.assertEqual(question.author, self.alice)
        self.assertEqual(question.source, Question.Source.MEMBER)

        self.client.force_login(self.bob)
        self.client.post(reverse("chiebukuro:question", args=[question.pk]), {"body": "Praxis am Stadtrand"})
        self.client.post(reverse("chiebukuro:question", args=[question.pk]), {"body": "Praxis am Stadtrand"})
        answer = Answer.objects.get()
        self.assertEqual(answer.nickname, "bob")
        question.refresh_from_db()
        self.assertIsNotNone(question.last_answered_at)

        self.client.post(reverse("chiebukuro:interest", args=[question.pk]))
        self.assertTrue(Interest.objects.filter(user=self.bob).exists())
        self.client.post(reverse("chiebukuro:interest", args=[question.pk]))
        self.assertFalse(Interest.objects.filter(user=self.bob).exists())

        # 自分の答えには「参考になった」を押せない
        self.client.post(reverse("chiebukuro:thanks", args=[answer.pk]))
        self.assertFalse(Thanks.objects.exists())
        self.client.force_login(self.alice)
        self.client.post(reverse("chiebukuro:thanks", args=[answer.pk]))
        self.assertTrue(Thanks.objects.filter(user=self.alice).exists())

    def test_guest_can_read_but_must_log_in_to_write(self):
        question = Question.objects.create(body="Q", theme="life")
        response = self.client.get(reverse("chiebukuro:question", args=[question.pk]))
        self.assertContains(response, "ログインして答える")
        response = self.client.post(reverse("chiebukuro:question", args=[question.pk]), {"body": "A"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Answer.objects.exists())
        self.assertEqual(self.client.get(reverse("chiebukuro:ask")).status_code, 302)

    def test_hidden_question_is_not_shown(self):
        question = Question.objects.create(body="消した質問", theme="life", status="hidden")
        self.assertEqual(self.client.get(reverse("chiebukuro:question", args=[question.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse("chiebukuro:home")), "消した質問")

    def test_report(self):
        question = Question.objects.create(body="Q", theme="life")
        self.client.force_login(self.alice)
        self.client.post(reverse("chiebukuro:report"), {"target": "question", "target_id": question.pk, "reason": "宣伝"})
        self.assertEqual(Report.objects.get().reason, "宣伝")


class ItemTests(BoardTestCase):

    def test_give_away_flow(self):
        self.client.force_login(self.alice)
        response = self.client.post(
            reverse("chiebukuro:item_new", args=["give"]),
            {"title": "ベビーカー", "body": "少し傷あり", "region": "zurich", "place": "Oerlikon", "agree": "yes"},
        )
        item = Item.objects.get()
        self.assertRedirects(response, reverse("chiebukuro:item", args=[item.pk]))
        self.assertEqual(item.state, Item.State.OPEN)

        # ルールの確認が必要
        self.client.post(reverse("chiebukuro:item_new", args=["give"]), {"title": "椅子"})
        self.assertEqual(Item.objects.count(), 1)

        self.assertContains(self.client.get(reverse("chiebukuro:give")), "ベビーカー")
        self.assertNotContains(self.client.get(reverse("chiebukuro:books")), "ベビーカー")

        self.client.force_login(self.bob)
        response = self.client.post(reverse("chiebukuro:item_request", args=[item.pk]), {"body": "ほしいです"})
        talk = ItemRequest.objects.get()
        self.assertRedirects(response, reverse("chiebukuro:talk", args=[talk.pk]))
        self.assertEqual(Message.objects.get().body, "ほしいです")

        # 出した人のマイページに未読が出る
        self.client.force_login(self.alice)
        response = self.client.get(reverse("chiebukuro:me"))
        self.assertContains(response, "ベビーカー")
        self.assertEqual(response.context["unread_talks"], 1)

        response = self.client.get(reverse("chiebukuro:talk", args=[talk.pk]))
        self.assertContains(response, "ほしいです")
        self.client.post(reverse("chiebukuro:talk", args=[talk.pk]), {"body": "土曜でどうですか"})
        self.client.post(reverse("chiebukuro:talk_choose", args=[talk.pk]))
        item.refresh_from_db()
        talk.refresh_from_db()
        self.assertEqual(item.state, Item.State.RESERVED)
        self.assertTrue(talk.is_chosen)

        # ほかの人はもう送れない
        carol = public_user("carol")
        self.client.force_login(carol)
        self.client.post(reverse("chiebukuro:item_request", args=[item.pk]), {"body": "私も"})
        self.assertEqual(ItemRequest.objects.count(), 1)
        # ほかの人のやりとりは見られない
        self.assertEqual(self.client.get(reverse("chiebukuro:talk", args=[talk.pk])).status_code, 404)

        self.client.force_login(self.alice)
        self.client.post(reverse("chiebukuro:item_state", args=[item.pk]), {"state": "done"})
        item.refresh_from_db()
        self.assertEqual(item.state, Item.State.DONE)
        self.assertNotContains(self.client.get(reverse("chiebukuro:give")), "ベビーカー")

    def test_book_labels(self):
        item = Item.objects.create(kind="book", title="はらぺこあおむし", owner=self.alice, state="reserved")
        self.assertEqual(item.state_label(), "貸し出し中")
        self.assertEqual(item.request_word, "借りたい")
        self.assertContains(self.client.get(reverse("chiebukuro:books")), "はらぺこあおむし")

    def test_owner_can_withdraw(self):
        item = Item.objects.create(kind="give", title="椅子", owner=self.alice)
        self.client.force_login(self.bob)
        self.client.post(reverse("chiebukuro:item_state", args=[item.pk]), {"delete": "yes"})
        item.refresh_from_db()
        self.assertEqual(item.status, "published")
        self.client.force_login(self.alice)
        self.client.post(reverse("chiebukuro:item_state", args=[item.pk]), {"delete": "yes"})
        item.refresh_from_db()
        self.assertEqual(item.status, "hidden")
        self.client.force_login(self.bob)
        self.assertEqual(self.client.get(reverse("chiebukuro:item", args=[item.pk])).status_code, 404)


class PostTests(BoardTestCase):

    def test_post_reply_like_profile(self):
        self.client.force_login(self.alice)
        response = self.client.post(reverse("chiebukuro:post_new"), {"body": "Migros にお餅がありました", "theme": "shopping", "region": "zurich"})
        self.assertRedirects(response, reverse("chiebukuro:home") + "?tab=new")
        post = Post.objects.get()
        self.assertEqual((post.theme, post.region, post.nickname), ("shopping", "zurich", "alice"))

        self.client.force_login(self.bob)
        self.client.post(reverse("chiebukuro:post", args=[post.pk]), {"body": "どこの店舗ですか？"})
        self.assertEqual(PostReply.objects.get().author, self.bob)
        self.client.post(reverse("chiebukuro:post_like", args=[post.pk]))
        self.assertTrue(PostLike.objects.filter(user=self.bob).exists())

        response = self.client.get(reverse("chiebukuro:profile", args=["alice"]))
        self.assertContains(response, "Migros にお餅がありました")
        self.assertContains(response, "👍 1")

        # 消すのは本人だけ
        self.client.post(reverse("chiebukuro:delete_post", args=[post.pk]))
        post.refresh_from_db()
        self.assertEqual(post.status, "published")
        self.client.force_login(self.alice)
        self.client.post(reverse("chiebukuro:delete_post", args=[post.pk]))
        post.refresh_from_db()
        self.assertEqual(post.status, "hidden")

    def test_write_menu_and_guest_redirect(self):
        self.assertContains(self.client.get(reverse("chiebukuro:new")), "つぶやく")
        self.assertEqual(self.client.get(reverse("chiebukuro:post_new")).status_code, 302)
