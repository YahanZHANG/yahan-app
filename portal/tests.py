from importlib import import_module

from django.apps import apps as django_apps
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from news.models import Article, NewsSource


SIGNUP_DATA = {
    "username": "hanako",
    "email": "",
    "password1": "Kome-2026-onigiri",
    "password2": "Kome-2026-onigiri",
}


class SignupTests(TestCase):

    def test_signup_logs_in_right_away_without_email(self):

        response = self.client.post(
            reverse("portal:signup"),
            SIGNUP_DATA,
        )

        self.assertRedirects(
            response,
            reverse("portal:nickname_setup"),
            fetch_redirect_response=False,
        )

        user = User.objects.get(username="hanako")
        self.assertTrue(user.is_active)
        self.assertTrue(user.groups.filter(name="public_users").exists())
        self.assertEqual(
            self.client.session["_auth_user_id"],
            str(user.pk),
        )

    def test_double_submit_does_not_say_already_used(self):

        self.client.post(reverse("portal:signup"), SIGNUP_DATA)
        self.client.logout()

        # 二度押し・戻って再送信
        response = self.client.post(
            reverse("portal:signup"),
            {**SIGNUP_DATA, "username": "Hanako "},
        )

        self.assertRedirects(
            response,
            reverse("portal:nickname_setup"),
            fetch_redirect_response=False,
        )
        self.assertEqual(User.objects.filter(username__iexact="hanako").count(), 1)

    def test_taken_username_with_other_password_still_errors(self):

        self.client.post(reverse("portal:signup"), SIGNUP_DATA)
        self.client.logout()

        response = self.client.post(
            reverse("portal:signup"),
            {**SIGNUP_DATA, "password1": "Other-pass-99x", "password2": "Other-pass-99x"},
        )

        self.assertContains(response, "すでに使用されています")

    def test_email_is_optional_but_unique(self):

        User.objects.create_user("taken", email="a@example.com", password="x")

        response = self.client.post(
            reverse("portal:signup"),
            {**SIGNUP_DATA, "email": "A@example.com"},
        )

        self.assertContains(response, "すでに登録されています")

    def test_login_with_new_account(self):

        self.client.post(reverse("portal:signup"), SIGNUP_DATA)
        self.client.logout()

        response = self.client.post(
            reverse("login"),
            {"username": "Hanako ", "password": SIGNUP_DATA["password1"]},
        )

        self.assertEqual(response.status_code, 302)


class ActivateUnverifiedSignupsTests(TestCase):

    def test_stuck_accounts_are_activated(self):

        group = Group.objects.create(name="public_users")
        stuck = User.objects.create_user("stuck", password="x", is_active=False)
        stuck.groups.add(group)
        disabled = User.objects.create_user("disabled", password="x", is_active=False)
        disabled.groups.add(group)
        disabled.last_login = timezone.now()
        disabled.save()

        migration = import_module(
            "portal.migrations.0004_activate_unverified_signups"
        )
        migration.activate_unverified_signups(django_apps, None)

        stuck.refresh_from_db()
        disabled.refresh_from_db()
        self.assertTrue(stuck.is_active)
        self.assertFalse(disabled.is_active)


class NewsArticleClickTests(TestCase):

    def setUp(self):

        source = NewsSource.objects.create(
            name="SRF",
            website_url="https://www.srf.ch",
            language="de",
        )
        self.article = Article.objects.create(
            source=source,
            source_url="https://www.srf.ch/news/1",
            original_language="de",
            title_original="Original",
            summary_original="Summary",
            published_at=timezone.now(),
        )
        self.url = reverse(
            "usage_analytics:public_news_article_click",
            args=[self.article.pk],
        )

    def test_guest_reaches_article(self):

        response = self.client.get(self.url)

        self.assertRedirects(
            response,
            "https://www.srf.ch/news/1",
            fetch_redirect_response=False,
        )

    def test_signed_up_user_reaches_article(self):

        user = User.objects.create_user("member", password="x")
        user.groups.add(Group.objects.create(name="public_users"))
        self.client.force_login(user)

        response = self.client.get(self.url)

        self.assertRedirects(
            response,
            "https://www.srf.ch/news/1",
            fetch_redirect_response=False,
        )

    def test_beacon_records_click_without_redirect(self):

        response = self.client.get(self.url + "?origin=/news/&beacon=1")

        self.assertEqual(response.status_code, 204)


class InstallGuideTests(TestCase):

    def test_install_pages_show_steps_and_qr(self):

        for name in ("washoku:install", "news:install"):
            response = self.client.get(reverse(name))
            self.assertContains(response, "ホーム画面に追加しよう")
            self.assertContains(response, "<svg", msg_prefix=name)


class HelpPageTests(TestCase):

    def test_help_page_and_links(self):

        response = self.client.get(reverse("portal:help") + "?from=washoku")
        self.assertContains(response, "困ったときは")
        self.assertContains(response, reverse("washoku:about") + "#feedback")

        self.assertContains(self.client.get(reverse("washoku:about")), reverse("portal:help"))
        self.assertContains(self.client.get(reverse("news:about")), reverse("portal:help"))
        self.assertContains(self.client.get(reverse("portal:home")), reverse("portal:help"))


class KeepLoginTests(TestCase):

    def test_login_is_extended_once_a_day(self):

        user = User.objects.create_user("keeper", password="x")
        self.client.force_login(user)

        first = self.client.get(reverse("portal:help"))
        self.assertIn("sessionid", first.cookies)

        # 同じ日の2回目は保存し直さない
        second = self.client.get(reverse("portal:help"))
        self.assertNotIn("sessionid", second.cookies)

        session = self.client.session
        session["_login_refreshed_at"] = 0
        session.save()

        third = self.client.get(reverse("portal:help"))
        self.assertIn("sessionid", third.cookies)
        self.assertEqual(third.cookies["sessionid"]["max-age"], 60 * 60 * 24 * 400)


class PortalAnnouncementTests(TestCase):

    def test_active_announcement_shows_on_top(self):

        from portal.models import PortalAnnouncement

        PortalAnnouncement.objects.create(message="ログインの不具合を直しました", link="/help/")
        PortalAnnouncement.objects.create(message="非表示のお知らせ", is_active=False)

        response = self.client.get(reverse("portal:home"))

        self.assertContains(response, "ログインの不具合を直しました")
        self.assertNotContains(response, "非表示のお知らせ")


class AdminHomeTests(TestCase):

    def test_admin_home_puts_inbox_first_and_folds_rare_apps(self):
        from django.contrib.auth import get_user_model
        from django.urls import reverse

        from washoku.models import Feedback

        admin = get_user_model().objects.create_user("boss", password="x", is_staff=True, is_superuser=True)
        Feedback.objects.create(message="要望")

        self.client.force_login(admin)
        response = self.client.get(reverse("admin:index"))

        self.assertContains(response, "和食 質問箱")
        self.assertContains(response, "Yapp 応援メッセージ")
        self.assertContains(response, "ほとんど使わないアプリ")
        self.assertContains(response, 'data-yh-key="app-washoku" open')
        self.assertContains(response, 'data-yh-key="app-feeding">')

        # 一覧ページの左メニューも「ほかのアプリ」にまとまる
        response = self.client.get(reverse("admin:washoku_feedback_changelist"))
        self.assertContains(response, "ほかのアプリ")
