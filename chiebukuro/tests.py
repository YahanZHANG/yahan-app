import uuid
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from pre_survey.models import Answer as SurveyAnswer
from pre_survey.models import Interest as SurveyInterest
from pre_survey.models import Question as SurveyQuestion

from .models import (
    Answer, BoardProfile, BoardSettings, Interest, Item, ItemRequest, Message, Notice, Notification, Poll, PollChoice, PollVote,
    Post, PostReply, Question, Reaction, Report, Sponsor, Thanks,
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
        for name in ["boardsettings", "question", "answer", "item", "itemrequest", "report", "post", "notice"]:
            self.assertEqual(self.client.get(reverse(f"admin:chiebukuro_{name}_changelist")).status_code, 200)


class HomeTests(BoardTestCase):

    def test_home_is_weekly_edition_without_new_post_list(self):
        from chiebukuro.models import Thanks

        Post.objects.create(body="Coop に枝豆がありました", author=self.alice, nickname="alice")
        Question.objects.create(body="答え待ちの質問", theme="life")
        answered = Question.objects.create(body="答えのある質問", theme="life")
        best = Answer.objects.create(question=answered, body="これが答え", author=self.bob, nickname="bob")
        Thanks.objects.create(answer=best, user=self.alice)
        Item.objects.create(kind="give", genre="kids", title="ベビーカー", owner=self.bob, photo_url="https://example.com/a.jpg")
        Item.objects.create(kind="give", genre="kids", title="写真なしの椅子", owner=self.bob)
        response = self.client.get(reverse("chiebukuro:home"))
        for text in ["今週の注目", "役に立った答え", "これが答え", "答え待ちの質問", "ベビーカー", "あなたの知恵を貸してください"]:
            self.assertContains(response, text)
        # つぶやきの新着・写真のないゆずりあいは HOME に出さない
        self.assertNotContains(response, "Coop に枝豆がありました")
        self.assertNotContains(response, "写真なしの椅子")
        # 下のメニュー: 本は出さない、つぶやきは出す
        for label in ["つぶやき", "質問", "ゆずりあい", "募集・告知"]:
            self.assertContains(response, f"<span>{label}</span>", html=False)
        self.assertNotContains(response, "本の貸し借り")

    def test_staff_pick_comes_first_in_featured(self):
        from chiebukuro.models import Thanks

        question = Question.objects.create(body="質問", theme="life")
        popular = Answer.objects.create(question=question, body="人気の答え")
        Thanks.objects.create(answer=popular, user=self.alice)
        Post.objects.create(body="運営のおすすめ", author=self.alice, nickname="alice", home_pick=True)
        response = self.client.get(reverse("chiebukuro:home"))
        featured = response.context["featured"]
        self.assertEqual(featured[0]["text"], "運営のおすすめ")
        self.assertEqual(featured[1]["text"], "人気の答え")

    def test_today_strip_shows_weather_and_rate(self):
        fake = {"weather": {"temp": 7, "emoji": "☀️", "label": "晴れ", "days": [{"max": 9, "min": 1}]}, "jpy": {"rate": 182.34, "change": 0.4}, "eur": None}
        with mock.patch("chiebukuro.views.today_in_switzerland", return_value=fake):
            response = self.client.get(reverse("chiebukuro:today"))
        self.assertContains(response, "7°")
        self.assertContains(response, "182.3")
        self.assertContains(response, "チューリッヒ")

    def test_region_is_remembered(self):
        Item.objects.create(kind="give", genre="other", title="チューリッヒの椅子", region="zurich", owner=self.bob)
        Item.objects.create(kind="give", genre="other", title="ジュネーブの机", region="geneva", owner=self.bob)
        response = self.client.get(reverse("chiebukuro:items") + "?region=zurich")
        self.assertContains(response, "チューリッヒの椅子")
        self.assertNotContains(response, "ジュネーブの机")
        # ほかのページでも同じ地域のまま
        response = self.client.get(reverse("chiebukuro:home"))
        self.assertNotContains(response, "ジュネーブの机")
        response = self.client.get(reverse("chiebukuro:items") + "?region=")
        self.assertContains(response, "ジュネーブの机")

    def test_profile_region_is_the_default(self):
        Item.objects.create(kind="give", genre="other", title="ジュネーブの机", region="geneva", owner=self.bob)
        BoardProfile.objects.create(user=self.alice, region="zurich")
        self.client.force_login(self.alice)
        self.assertNotContains(self.client.get(reverse("chiebukuro:items")), "ジュネーブの机")

    def test_search_everything(self):
        Post.objects.create(body="保険の話", author=self.alice, nickname="alice")
        Question.objects.create(body="保険はどこ？", theme="money")
        Item.objects.create(kind="give", genre="books", title="保険の本", owner=self.bob)
        response = self.client.get(reverse("chiebukuro:search") + "?q=保険")
        for text in ["保険の話", "保険はどこ？", "保険の本"]:
            self.assertContains(response, text)


class QuestionTests(BoardTestCase):

    def test_question_list_sorts_and_filters(self):
        dentist = Question.objects.create(body="歯医者は？", theme="health", region="zurich")
        best = Answer.objects.create(question=dentist, body="Smile がいいです", nickname="Yunyun")
        Answer.objects.create(question=dentist, body="日本で治す", nickname="空")
        Thanks.objects.create(answer=best, user=self.alice)
        Question.objects.create(body="お土産は？", theme="shopping")
        Question.objects.create(body="ジュネーブの公園は？", theme="outing", region="geneva")
        url = reverse("chiebukuro:questions")

        response = self.client.get(url)
        self.assertContains(response, "歯医者は？")
        self.assertContains(response, "Smile がいいです")  # いちばん参考になった答えをちら見せ
        self.assertContains(response, "お土産は？")

        response = self.client.get(url + "?sort=popular")
        self.assertContains(response, "歯医者は？")
        self.assertNotContains(response, "お土産は？")

        response = self.client.get(url + "?sort=open")
        self.assertContains(response, "お土産は？")
        self.assertNotContains(response, "歯医者は？")

        response = self.client.get(url + "?sort=open&region=zurich")
        self.assertContains(response, "お土産は？")
        self.assertNotContains(response, "ジュネーブの公園は？")

        response = self.client.get(url + "?sort=open&theme=outing&region=")
        self.assertContains(response, "ジュネーブの公園は？")
        self.assertNotContains(response, "お土産は？")

        # キーワード: 答えの中も探す
        response = self.client.get(url + "?q=Smile")
        self.assertContains(response, "「Smile」の質問 1件")

    def test_wanted_questions_first_in_popular(self):
        popular = Question.objects.create(body="人気", theme="life", survey_interest_count=2)
        quiet = Question.objects.create(body="静か", theme="life")
        for question in (popular, quiet):
            Answer.objects.create(question=question, body="A")
        Interest.objects.create(question=quiet, user=self.alice)
        response = self.client.get(reverse("chiebukuro:questions") + "?sort=popular")
        self.assertEqual([q.body for q in response.context["page"].object_list], ["人気", "静か"])

    def test_best_answer_first_on_question_page(self):
        question = Question.objects.create(body="Q", theme="life")
        Answer.objects.create(question=question, body="最初の答え")
        helpful = Answer.objects.create(question=question, body="役に立つ答え")
        Thanks.objects.create(answer=helpful, user=self.alice)
        response = self.client.get(reverse("chiebukuro:question", args=[question.pk]))
        self.assertEqual(response.context["answers"][0], helpful)
        self.assertContains(response, "いちばん参考になった回答")

    def test_ask_answer_interest_thanks_and_notifications(self):
        self.client.force_login(self.alice)
        response = self.client.post(reverse("chiebukuro:ask"), {"body": "おすすめの小児科は？", "theme": "childcare", "question_region": "zurich"})
        question = Question.objects.get()
        self.assertRedirects(response, reverse("chiebukuro:question", args=[question.pk]))
        self.assertEqual((question.author, question.source, question.region), (self.alice, Question.Source.MEMBER, "zurich"))

        carol = public_user("carol")
        Interest.objects.create(question=question, user=carol)

        self.client.force_login(self.bob)
        self.client.post(reverse("chiebukuro:question", args=[question.pk]), {"body": "Praxis am Stadtrand"})
        self.client.post(reverse("chiebukuro:question", args=[question.pk]), {"body": "Praxis am Stadtrand"})
        answer = Answer.objects.get()
        self.assertEqual(answer.nickname, "bob")
        question.refresh_from_db()
        self.assertIsNotNone(question.last_answered_at)

        # 質問した人と「知りたい」の人に🔔
        self.assertEqual(Notification.objects.filter(user=self.alice, kind="answer").count(), 1)
        self.assertEqual(Notification.objects.filter(user=carol, kind="answer").count(), 1)
        self.assertFalse(Notification.objects.filter(user=self.bob).exists())

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

        # 🔔: 未読の数 → 開くと既読
        response = self.client.get(reverse("chiebukuro:home"))
        self.assertEqual(response.context["unread"], 1)
        response = self.client.get(reverse("chiebukuro:notifications"))
        self.assertContains(response, "答えがつきました")
        self.assertEqual(self.client.get(reverse("chiebukuro:home")).context["unread"], 0)

    def test_guest_can_read_but_must_log_in_to_write(self):
        question = Question.objects.create(body="Q", theme="life")
        response = self.client.get(reverse("chiebukuro:question", args=[question.pk]))
        self.assertContains(response, "ログインして回答する")
        response = self.client.post(reverse("chiebukuro:question", args=[question.pk]), {"body": "A"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Answer.objects.exists())
        self.assertEqual(self.client.get(reverse("chiebukuro:ask")).status_code, 302)

    def test_hidden_question_is_not_shown(self):
        question = Question.objects.create(body="消した質問", theme="life", status="hidden")
        self.assertEqual(self.client.get(reverse("chiebukuro:question", args=[question.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse("chiebukuro:questions")), "消した質問")

    def test_report(self):
        question = Question.objects.create(body="Q", theme="life")
        self.client.force_login(self.alice)
        response = self.client.post(reverse("chiebukuro:report"), {"target": "question", "target_id": question.pk, "reason": "宣伝", "next": "https://evil.example/"})
        self.assertEqual(Report.objects.get().reason, "宣伝")
        self.assertEqual(response["Location"], reverse("chiebukuro:home"))


class ItemTests(BoardTestCase):

    def test_give_away_flow(self):
        self.client.force_login(self.alice)
        response = self.client.post(
            reverse("chiebukuro:item_new"),
            {"kind": "give", "genre": "kids", "title": "ベビーカー", "body": "少し傷あり", "item_region": "zurich", "place": "Oerlikon", "agree": "yes"},
        )
        item = Item.objects.get()
        self.assertRedirects(response, reverse("chiebukuro:item", args=[item.pk]))
        self.assertEqual((item.state, item.genre, item.region), (Item.State.OPEN, "kids", "zurich"))

        # ルールの確認が必要
        self.client.post(reverse("chiebukuro:item_new"), {"kind": "give", "genre": "other", "title": "椅子"})
        self.assertEqual(Item.objects.count(), 1)

        self.assertContains(self.client.get(reverse("chiebukuro:items") + "?kind=give"), "ベビーカー")
        self.assertNotContains(self.client.get(reverse("chiebukuro:items") + "?kind=lend"), "ベビーカー")
        self.assertContains(self.client.get(reverse("chiebukuro:items") + "?genre=kids"), "ベビーカー")

        self.client.force_login(self.bob)
        response = self.client.post(reverse("chiebukuro:item_request", args=[item.pk]), {"body": "ほしいです"})
        talk = ItemRequest.objects.get()
        self.assertRedirects(response, reverse("chiebukuro:talk", args=[talk.pk]))
        self.assertEqual(Message.objects.get().body, "ほしいです")

        # 出した人に🔔、マイページにやりとり
        self.client.force_login(self.alice)
        response = self.client.get(reverse("chiebukuro:me"))
        self.assertEqual(response.context["unread"], 1)
        self.assertContains(self.client.get(reverse("chiebukuro:my_list", args=["talks"])), "ベビーカー")

        response = self.client.get(reverse("chiebukuro:talk", args=[talk.pk]))
        self.assertContains(response, "ほしいです")
        self.assertEqual(response.context["unread"], 0)
        self.client.post(reverse("chiebukuro:talk", args=[talk.pk]), {"body": "土曜でどうですか"})
        self.assertEqual(Notification.objects.filter(user=self.bob, kind="talk").count(), 1)
        self.client.post(reverse("chiebukuro:talk_choose", args=[talk.pk]))
        item.refresh_from_db()
        talk.refresh_from_db()
        self.assertEqual(item.state, Item.State.RESERVED)
        self.assertTrue(talk.is_chosen)
        self.assertTrue(Notification.objects.filter(user=self.bob, kind="chosen").exists())

        # ほかの人はもう送れない・やりとりは見られない
        carol = public_user("carol")
        self.client.force_login(carol)
        self.client.post(reverse("chiebukuro:item_request", args=[item.pk]), {"body": "私も"})
        self.assertEqual(ItemRequest.objects.count(), 1)
        self.assertEqual(self.client.get(reverse("chiebukuro:talk", args=[talk.pk])).status_code, 404)

        self.client.force_login(self.alice)
        self.client.post(reverse("chiebukuro:item_state", args=[item.pk]), {"state": "done"})
        item.refresh_from_db()
        self.assertEqual(item.state, Item.State.DONE)
        self.assertNotContains(self.client.get(reverse("chiebukuro:items")), "ベビーカー")

    def test_kind_words(self):
        cases = {
            "give": ("ほしい", "受付中"),
            "want": ("ゆずれます", "さがしています"),
            "lend": ("借りたい", "貸し出しできます"),
            "borrow": ("貸せます", "さがしています"),
        }
        for kind, (word, label) in cases.items():
            item = Item(kind=kind, title="x", owner=self.alice)
            self.assertEqual((item.request_word, item.state_label()), (word, label))
        self.assertEqual(Item(kind="lend", state="reserved").state_label(), "貸し出し中")

    def test_want_post_gets_offers(self):
        item = Item.objects.create(kind="want", genre="sports", title="スキーブーツ 20cm", owner=self.alice)
        self.client.force_login(self.bob)
        self.assertContains(self.client.get(reverse("chiebukuro:item", args=[item.pk])), "「ゆずれます」を送る")
        self.client.post(reverse("chiebukuro:item_request", args=[item.pk]), {"body": "使っていないのがあります"})
        self.assertEqual(ItemRequest.objects.get().item, item)

    def test_old_urls_redirect(self):
        self.assertRedirects(self.client.get("/swiss-board/give/"), "/swiss-board/items/?kind=give", fetch_redirect_response=False)

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


class NoticeTests(BoardTestCase):

    def data(self, **extra):
        return {"kind": "lesson", "title": "書道教室", "body": "毎週土曜", "notice_region": "zurich", "agree": "yes", **extra}

    def test_one_notice_per_person_and_inquiry(self):
        self.client.force_login(self.alice)
        response = self.client.post(reverse("chiebukuro:notice_new"), self.data(link="https://example.com/"))
        notice = Notice.objects.get()
        self.assertRedirects(response, reverse("chiebukuro:notice", args=[notice.pk]))
        self.assertTrue(notice.is_pr)
        self.assertEqual((notice.expires_at - notice.created_at).days, 30)

        # 2件目は出せない (いまの告知へ)
        response = self.client.get(reverse("chiebukuro:notice_new"))
        self.assertRedirects(response, reverse("chiebukuro:notice", args=[notice.pk]))
        self.client.post(reverse("chiebukuro:notice_new"), self.data(title="2件目"))
        self.assertEqual(Notice.objects.count(), 1)

        page = self.client.get(reverse("chiebukuro:notices") + "?kind=lesson")
        self.assertContains(page, "書道教室")
        self.assertContains(page, ">PR<", html=False)

        self.client.force_login(self.bob)
        self.client.post(reverse("chiebukuro:notice_request", args=[notice.pk]), {"body": "見学できますか？"})
        talk = ItemRequest.objects.get()
        self.assertEqual(talk.notice, notice)
        self.assertTrue(Notification.objects.filter(user=self.alice, kind="talk").exists())
        self.assertContains(self.client.get(reverse("chiebukuro:talk", args=[talk.pk])), "見学できますか？")
        self.client.force_login(self.alice)
        self.assertContains(self.client.get(reverse("chiebukuro:my_list", args=["items"])), "書道教室")

        # 取り下げると、すぐ新しく出せる
        self.client.post(reverse("chiebukuro:notice_withdraw", args=[notice.pk]))
        self.client.post(reverse("chiebukuro:notice_new"), self.data(title="新しい告知"))
        self.assertEqual(Notice.objects.filter(status="published").get().title, "新しい告知")

    def test_expired_notices_disappear_and_link_must_be_url(self):
        old = Notice.objects.create(kind="event", title="終わった会", body="x", owner=self.alice)
        Notice.objects.filter(pk=old.pk).update(expires_at=timezone.now() - timezone.timedelta(days=1))
        self.assertNotContains(self.client.get(reverse("chiebukuro:notices")), "終わった会")
        self.client.force_login(self.alice)
        self.client.post(reverse("chiebukuro:notice_new"), self.data(link="javascript:alert(1)"))
        self.assertEqual(Notice.objects.count(), 1)

    def test_sitter_notice_shows_safety_notes(self):
        notice = Notice.objects.create(kind="sitter_find", title="平日のシッター", body="x", owner=self.alice)
        self.assertContains(self.client.get(reverse("chiebukuro:notice", args=[notice.pk])), "保護者もいっしょに")


class PostTests(BoardTestCase):

    def test_timeline_page_post_reply_like_profile(self):
        self.client.force_login(self.alice)
        response = self.client.post(reverse("chiebukuro:post_new"), {"body": "Migros にお餅がありました", "theme": "shopping", "post_region": "zurich"})
        self.assertRedirects(response, reverse("chiebukuro:posts"))
        post = Post.objects.get()
        self.assertEqual((post.theme, post.region, post.nickname), ("shopping", "zurich", "alice"))
        self.assertContains(self.client.get(reverse("chiebukuro:posts")), "Migros にお餅がありました")
        self.assertNotContains(self.client.get(reverse("chiebukuro:posts") + "?theme=health"), "Migros にお餅")

        self.client.force_login(self.bob)
        self.client.post(reverse("chiebukuro:post", args=[post.pk]), {"body": "どこの店舗ですか？"})
        self.assertEqual(PostReply.objects.get().author, self.bob)
        self.assertTrue(Notification.objects.filter(user=self.alice, kind="reply").exists())
        response = self.client.post(reverse("chiebukuro:stamp"), {"target": "post", "target_id": post.pk, "stamp": "helpful", "next": "https://evil.example/"})
        self.assertEqual(response["Location"], reverse("chiebukuro:post", args=[post.pk]))
        self.assertTrue(Reaction.objects.filter(user=self.bob, stamp="helpful").exists())
        self.assertTrue(Notification.objects.filter(user=self.alice, kind="stamp").exists())

        response = self.client.get(reverse("chiebukuro:profile", args=["alice"]))
        self.assertContains(response, "Migros にお餅がありました")
        self.assertContains(response, "<b>1</b>役に立った", html=False)

        # 消すのは本人だけ
        self.client.post(reverse("chiebukuro:delete_post", args=[post.pk]))
        post.refresh_from_db()
        self.assertEqual(post.status, "published")
        self.client.force_login(self.alice)
        self.client.post(reverse("chiebukuro:delete_post", args=[post.pk]))
        post.refresh_from_db()
        self.assertEqual(post.status, "hidden")

    def test_profile_edit(self):
        self.client.force_login(self.alice)
        self.client.post(reverse("chiebukuro:profile_edit"), {"nickname": "ありす", "home_region": "basel", "intro": "バーゼル在住です"})
        profile = BoardProfile.objects.get(user=self.alice)
        self.assertEqual((profile.region, profile.intro), ("basel", "バーゼル在住です"))
        response = self.client.get(reverse("chiebukuro:profile", args=["alice"]))
        self.assertContains(response, "ありす")
        self.assertContains(response, "バーゼル在住です")

    def test_write_menu_and_guest_redirect(self):
        response = self.client.get(reverse("chiebukuro:new"))
        for text in ["つぶやく", "質問する", "ゆずりあいに出す", "募集・告知する"]:
            self.assertContains(response, text)
        self.assertEqual(self.client.get(reverse("chiebukuro:post_new")).status_code, 302)
        self.assertEqual(self.client.get(reverse("chiebukuro:notifications")).status_code, 302)

    def test_every_page_renders(self):
        question = Question.objects.create(body="Q", theme="life")
        item = Item.objects.create(kind="lend", genre="books", title="絵本", owner=self.alice)
        notice = Notice.objects.create(kind="event", title="会", body="x", owner=self.alice)
        post = Post.objects.create(body="p", author=self.alice, nickname="alice")
        self.client.force_login(self.bob)
        urls = [
            reverse("chiebukuro:home"), reverse("chiebukuro:posts"), reverse("chiebukuro:questions"),
            reverse("chiebukuro:items"), reverse("chiebukuro:notices"), reverse("chiebukuro:notifications"),
            reverse("chiebukuro:me"), reverse("chiebukuro:profile_edit"), reverse("chiebukuro:new"),
            reverse("chiebukuro:search") + "?q=x", reverse("chiebukuro:ask"), reverse("chiebukuro:item_new") + "?kind=borrow",
            reverse("chiebukuro:notice_new"), reverse("chiebukuro:question", args=[question.pk]),
            reverse("chiebukuro:item", args=[item.pk]), reverse("chiebukuro:notice", args=[notice.pk]),
            reverse("chiebukuro:post", args=[post.pk]), reverse("chiebukuro:profile", args=["alice"]),
        ]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 200, url)


class HomeExtrasTests(BoardTestCase):

    def test_poll_vote_as_guest_and_member(self):
        poll = Poll.objects.create(question="スイスで一番好きな季節は？")
        spring = PollChoice.objects.create(poll=poll, label="春", order=1)
        autumn = PollChoice.objects.create(poll=poll, label="秋", order=2)
        response = self.client.get(reverse("chiebukuro:home"))
        self.assertContains(response, "スイスで一番好きな季節は？")
        self.assertContains(response, "答えると結果が見られます")
        # ゲストはブラウザごとに1票 (cookie)
        self.client.post(reverse("chiebukuro:poll_vote", args=[poll.pk]), {"choice": spring.pk})
        self.client.post(reverse("chiebukuro:poll_vote", args=[poll.pk]), {"choice": autumn.pk})
        self.assertEqual(PollVote.objects.get().choice, autumn)
        self.assertContains(self.client.get(reverse("chiebukuro:home")), "100%")
        self.client.force_login(self.alice)
        self.client.post(reverse("chiebukuro:poll_vote", args=[poll.pk]), {"choice": spring.pk})
        self.assertEqual(PollVote.objects.count(), 2)
        self.assertContains(self.client.get(reverse("chiebukuro:polls")), "50%")

    def test_sponsor_slot_and_click(self):
        self.assertContains(self.client.get(reverse("chiebukuro:home")), "広告を出せます")
        sponsor = Sponsor.objects.create(name="和ショップ", title="日本の食材を宅配", link="https://example.com/")
        self.assertContains(self.client.get(reverse("chiebukuro:home")), "日本の食材を宅配")
        response = self.client.get(reverse("chiebukuro:sponsor", args=[sponsor.pk]))
        self.assertEqual(response["Location"], "https://example.com/")
        sponsor.refresh_from_db()
        self.assertEqual(sponsor.clicks, 1)


class StampAndSettingsTests(BoardTestCase):

    def test_stamps_on_answers_and_replies(self):
        question = Question.objects.create(body="Q", theme="life")
        answer = Answer.objects.create(question=question, body="A", author=self.alice, nickname="alice")
        post = Post.objects.create(body="p", author=self.alice, nickname="alice")
        reply = PostReply.objects.create(post=post, body="r", author=self.alice, nickname="alice")
        self.client.force_login(self.bob)
        for target, obj in (("answer", answer), ("reply", reply)):
            self.client.post(reverse("chiebukuro:stamp"), {"target": target, "target_id": obj.pk, "stamp": "thanks"})
        self.client.post(reverse("chiebukuro:stamp"), {"target": "answer", "target_id": answer.pk, "stamp": "like"})
        self.assertEqual(Reaction.objects.count(), 3)
        response = self.client.get(reverse("chiebukuro:question", args=[question.pk]))
        self.assertContains(response, "<span>ありがとう</span><b>1</b>", html=False)
        # もう一度押すと取り消し
        self.client.post(reverse("chiebukuro:stamp"), {"target": "answer", "target_id": answer.pk, "stamp": "like"})
        self.assertEqual(Reaction.objects.count(), 2)
        # 自分の書きこみには押せない
        self.client.force_login(self.alice)
        self.client.post(reverse("chiebukuro:stamp"), {"target": "answer", "target_id": answer.pk, "stamp": "like"})
        self.assertEqual(Reaction.objects.count(), 2)

    def test_settings_save_theme_and_push_choices(self):
        from travel.models import UserProfile

        self.client.force_login(self.alice)
        self.assertContains(self.client.get(reverse("chiebukuro:settings")), "プッシュ通知の頻度")
        self.client.post(reverse("chiebukuro:settings"), {"theme": "dark", "push_frequency": "daily", "push_answer": "1", "push_stamp": "1"})
        profile = BoardProfile.objects.get(user=self.alice)
        self.assertEqual((profile.push_frequency, profile.push_answer, profile.push_reply, profile.push_stamp), ("daily", True, False, True))
        self.assertEqual(UserProfile.objects.get(user=self.alice).theme_preference, "dark")
        self.assertContains(self.client.get(reverse("chiebukuro:me")), 'data-yapp-theme="dark"', html=False)

    def test_push_follows_settings(self):
        from unittest import mock

        from chiebukuro.models import PushDevice
        from chiebukuro.push import send_daily_digest

        PushDevice.objects.create(user=self.alice, endpoint="https://push.example/a", p256dh="x", auth="y")
        question = Question.objects.create(body="Q", theme="life", author=self.alice)
        with mock.patch("washoku.push.is_configured", return_value=True), \
                mock.patch("chiebukuro.push.send", return_value=1) as send, \
                mock.patch("chiebukuro.push.threading.Thread") as thread:
            thread.side_effect = lambda target, daemon: mock.Mock(start=target)
            self.client.force_login(self.bob)
            self.client.post(reverse("chiebukuro:question", args=[question.pk]), {"body": "答えです"})
            self.assertEqual(send.call_count, 1)
            self.assertIn("答えがつきました", send.call_args[0][2])

            BoardProfile.objects.create(user=self.alice, push_frequency="daily")
            self.client.post(reverse("chiebukuro:question", args=[question.pk]), {"body": "もうひとつ"})
            self.assertEqual(send.call_count, 1)
            self.assertEqual(send_daily_digest(), 1)
            self.assertIn("未読のお知らせが2件", send.call_args[0][2])

    def test_photo_on_post_and_answer(self):
        from unittest import mock

        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.force_login(self.alice)
        with mock.patch("chiebukuro.views.upload_board_photo", return_value="https://res.example/p.webp"):
            self.client.post(reverse("chiebukuro:post_new"), {"body": "写真つき", "photo": SimpleUploadedFile("a.jpg", b"x", "image/jpeg")})
            question = Question.objects.create(body="Q", theme="life")
            self.client.post(reverse("chiebukuro:question", args=[question.pk]), {"body": "写真の答え", "photo": SimpleUploadedFile("a.jpg", b"x", "image/jpeg")})
        self.assertEqual(Post.objects.get().photo_url, "https://res.example/p.webp")
        self.assertEqual(Answer.objects.get().photo_url, "https://res.example/p.webp")
        self.assertContains(self.client.get(reverse("chiebukuro:posts")), "https://res.example/p.webp")
        # 写真を保存できないときは、書きこみも残さずに知らせる
        with mock.patch("chiebukuro.views.upload_board_photo", side_effect=Exception("down")):
            response = self.client.post(reverse("chiebukuro:post_new"), {"body": "失敗", "photo": SimpleUploadedFile("b.jpg", b"x", "image/jpeg")})
        self.assertContains(response, "写真を保存できませんでした")
        self.assertEqual(Post.objects.count(), 1)

    def test_my_lists(self):
        self.client.force_login(self.alice)
        for section in ["talks", "posts", "questions", "answers", "wanted", "items"]:
            self.assertEqual(self.client.get(reverse("chiebukuro:my_list", args=[section])).status_code, 200, section)
        self.assertEqual(self.client.get(reverse("chiebukuro:my_list", args=["nope"])).status_code, 404)


class FaceTests(BoardTestCase):

    def test_illustration_avatar_is_saved_and_shown(self):
        from chiebukuro.models import BoardProfile

        self.client.force_login(self.alice)
        response = self.client.post(reverse("chiebukuro:profile_edit"), {
            "nickname": "ありす", "avatar_kind": "illust",
            "av_bg": "mint", "av_hair": "bob", "av_glasses": "round", "av_skin": "9", "av_mouth": "grin",
        })
        self.assertEqual(response.status_code, 302)
        profile = BoardProfile.objects.get(user=self.alice)
        self.assertEqual(profile.avatar_kind, "illust")
        self.assertEqual(profile.avatar_parts["hair"], "bob")
        self.assertEqual(profile.avatar_parts["skin"], "2")  # 知らない値はふつうに戻す
        Post.objects.create(body="こんにちは", author=self.alice, nickname="ありす")
        page = self.client.get(reverse("chiebukuro:posts"))
        self.assertContains(page, "#C9EAD3")  # ミントの背景のイラスト

    def test_photo_avatar_needs_a_photo(self):
        self.client.force_login(self.alice)
        response = self.client.post(reverse("chiebukuro:profile_edit"), {"nickname": "ありす", "avatar_kind": "photo"})
        self.assertContains(response, "写真を選んでください。")
        with mock.patch("chiebukuro.views.upload_board_photo", return_value="https://res.cloudinary.com/x/face.webp"):
            from django.core.files.uploadedfile import SimpleUploadedFile

            response = self.client.post(reverse("chiebukuro:profile_edit"), {
                "nickname": "ありす", "avatar_kind": "photo", "photo": SimpleUploadedFile("a.jpg", b"x", content_type="image/jpeg"),
            })
        self.assertEqual(response.status_code, 302)
        self.assertContains(self.client.get(reverse("chiebukuro:me")), "https://res.cloudinary.com/x/face.webp")

    def test_avatar_preview_is_svg(self):
        response = self.client.get(reverse("chiebukuro:avatar_preview") + "?av_bg=red&av_hair=cap")
        self.assertEqual(response["Content-Type"], "image/svg+xml")
        self.assertContains(response, "#E45B63")


class SeasonTests(BoardTestCase):

    def test_auto_season_by_date(self):
        import datetime

        from chiebukuro.models import BoardSettings

        board = BoardSettings.current()
        self.assertEqual(board.season(datetime.date(2026, 10, 25)), "halloween")
        self.assertEqual(board.season(datetime.date(2026, 12, 10)), "christmas")
        self.assertEqual(board.season(datetime.date(2027, 1, 3)), "newyear")
        self.assertEqual(board.season(datetime.date(2026, 8, 1)), "nationalday")
        self.assertEqual(board.season(datetime.date(2026, 6, 10)), "")
        board.hero_season = "none"
        self.assertEqual(board.season(datetime.date(2026, 12, 10)), "")
        board.hero_season = "spring"
        self.assertEqual(board.season(datetime.date(2026, 6, 10)), "spring")

    def test_home_hero_shows_big_date_and_season(self):
        from chiebukuro.models import BoardSettings

        board = BoardSettings.current()
        board.hero_season = "christmas"
        board.save()
        response = self.client.get(reverse("chiebukuro:home"))
        self.assertContains(response, 'data-season="christmas"')
        self.assertContains(response, "🎄 アドベント")
        self.assertContains(response, "cb-hero-md")
        self.assertNotContains(response, "cb-scene")
        self.assertNotContains(response, "スイスで暮らす日本人の、知恵と助け合い")


class JapanCalendarTests(TestCase):

    def test_lunar_new_year_and_leap_month(self):
        import datetime

        from chiebukuro.japan_calendar import lunar_date, rokuyo

        self.assertEqual(lunar_date(datetime.date(2026, 2, 17)), (1, 1, False))
        self.assertEqual(rokuyo(datetime.date(2026, 2, 17)), "先勝")  # 旧暦1月1日はいつも先勝
        self.assertEqual(lunar_date(datetime.date(2025, 10, 6)), (8, 15, False))  # 中秋の名月
        self.assertEqual(lunar_date(datetime.date(2023, 3, 22)), (2, 1, True))  # 閏2月

    def test_full_moon(self):
        import datetime

        from chiebukuro.japan_calendar import moon

        self.assertEqual(moon(datetime.datetime(2026, 11, 24, 15, tzinfo=datetime.timezone.utc))["name"], "満月")
        self.assertEqual(moon(datetime.datetime(2026, 11, 9, 12, tzinfo=datetime.timezone.utc))["emoji"], "🌑")


class RulesAgreementTests(BoardTestCase):

    def test_rules_dialog_until_agreed(self):
        self.client.force_login(self.alice)
        page = self.client.get(reverse("chiebukuro:posts"))
        self.assertContains(page, "cb-rules-dialog")
        self.assertContains(page, "data-rules")
        self.assertEqual(self.client.post(reverse("chiebukuro:rules_agree")).status_code, 200)
        self.assertNotContains(self.client.get(reverse("chiebukuro:posts")), "cb-rules-dialog")


class WeatherHereTests(BoardTestCase):

    def test_weather_for_current_location(self):
        fake = {"weather": {"temp": 3, "emoji": "❄️", "label": "雪", "days": []}, "jpy": None, "eur": None}
        with mock.patch("chiebukuro.views.today_in_switzerland", return_value=fake) as today:
            response = self.client.get(reverse("chiebukuro:today") + "?lat=46.95&lon=7.45")
        today.assert_called_with("bern")
        self.assertContains(response, "現在地（ベルン付近）")
        self.assertContains(response, 'data-sky="snow"')
        with mock.patch("chiebukuro.views.today_in_switzerland", return_value=fake) as today:
            self.client.get(reverse("chiebukuro:today") + "?lat=35.68&lon=139.76")  # 東京: スイスの外
        today.assert_called_with("")
