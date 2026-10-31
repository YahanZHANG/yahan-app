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


class AdminRareAppsTests(TestCase):

    def test_admin_folds_rarely_used_apps(self):
        from django.contrib.auth import get_user_model
        from django.urls import reverse

        admin = get_user_model().objects.create_user("boss", password="x", is_staff=True, is_superuser=True)
        self.client.force_login(admin)

        response = self.client.get(reverse("admin:index"))
        html = response.content.decode()
        self.assertIn("ほとんど使わないアプリ", html)
        self.assertLess(html.index("app-washoku"), html.index("yapp-admin-rare"))
        self.assertGreater(html.index("app-feeding"), html.index("yapp-admin-rare"))

        # 一覧ページの左メニューも同じ
        response = self.client.get(reverse("admin:washoku_feedback_changelist"))
        self.assertContains(response, "yapp-nav-more")
class AppIdeaTests(TestCase):

    def test_idea_is_saved_and_thanked(self):

        from portal.models import AppIdea

        response = self.client.post(
            reverse("portal:send_app_idea"),
            {"idea": "病院を日本語で探せるアプリ", "contact": "たろう"},
        )

        self.assertRedirects(response, reverse("portal:home") + "?idea=sent#ideas", fetch_redirect_response=False)
        self.assertEqual(AppIdea.objects.get().contact, "たろう")
        self.assertContains(self.client.get(reverse("portal:home") + "?idea=sent"), "アイデアを受け取りました")

    def test_bot_trap_is_not_saved(self):

        from portal.models import AppIdea

        self.client.post(reverse("portal:send_app_idea"), {"idea": "spam", "website": "http://spam"})

        self.assertFalse(AppIdea.objects.exists())


class PortalHomeTests(TestCase):

    def test_latest_news_and_share_tags(self):

        source = NewsSource.objects.create(name="SRF", website_url="https://www.srf.ch", language="de")
        Article.objects.create(
            source=source,
            source_url="https://www.srf.ch/a1",
            original_language="ja",
            title_original="チューリッヒで初雪",
            published_at=timezone.now(),
        )

        response = self.client.get(reverse("portal:home"))

        self.assertContains(response, "チューリッヒで初雪")
        self.assertContains(response, 'property="og:image"')

    def test_season_can_be_fixed_in_admin(self):

        from portal.models import PortalSettings

        settings_row = PortalSettings.load()
        settings_row.season = "winter"
        settings_row.save()

        response = self.client.get(reverse("portal:home"))

        self.assertContains(response, "season-winter")

        settings_row.season = "late_autumn"
        settings_row.save()

        response = self.client.get(reverse("portal:home"))

        self.assertContains(response, "scene-autumn")
        self.assertContains(response, "data-autumn-leaves")


class SeasonCalendarTests(TestCase):

    def test_events_and_seasons_by_date(self):

        from datetime import date

        from portal.seasons import easter_sunday, theme_for

        self.assertEqual(easter_sunday(2027), date(2027, 3, 28))
        self.assertEqual(theme_for(date(2027, 1, 3)), "newyear")
        self.assertEqual(theme_for(date(2026, 12, 31)), "newyear")
        self.assertEqual(theme_for(date(2026, 12, 28)), "winter")
        self.assertEqual(theme_for(date(2027, 3, 27)), "easter")  # 桜の期間より短いイースターを優先
        self.assertEqual(theme_for(date(2027, 3, 20)), "sakura")
        self.assertEqual(theme_for(date(2027, 4, 19)), "sechselaeuten")
        self.assertEqual(theme_for(date(2027, 6, 3)), "early_summer")
        self.assertEqual(theme_for(date(2027, 8, 10)), "midsummer")
        self.assertEqual(theme_for(date(2026, 10, 27)), "halloween")
        self.assertEqual(theme_for(date(2026, 11, 27)), "blackfriday")
        self.assertEqual(theme_for(date(2026, 11, 10)), "late_autumn")
        self.assertEqual(theme_for(date(2026, 12, 24)), "christmas")


class PortalThemeTextTests(TestCase):

    def test_catch_can_be_changed_in_admin(self):

        from portal.models import PortalSettings, PortalThemeText

        settings_row = PortalSettings.load()
        settings_row.season = "winter"
        settings_row.save()
        PortalThemeText.objects.create(theme="winter", title="寒い日は", headline="")

        response = self.client.get(reverse("portal:home"))

        self.assertContains(response, "寒い日は")
        self.assertContains(response, "スイスを楽しもう。")  # 空の行は元の文言のまま


class ManageAppsReturnTests(TestCase):
    """My Account から、来たアプリに戻れる"""

    def setUp(self):
        from travel.models import UserProfile

        self.user = User.objects.create_user("hanako", password="x")
        UserProfile.objects.update_or_create(
            user=self.user,
            defaults={"password_setup_completed": True, "nickname_setup_completed": True, "nickname": "はなこ"},
        )
        self.client.force_login(self.user)

    def test_back_button_and_nickname_save_return_to_the_app(self):

        url = reverse("portal:manage_apps") + "?next=/washoku/me/"
        page = self.client.get(url)
        self.assertContains(page, "スイスで和食へ戻る")
        self.assertContains(page, 'href="/washoku/me/"')

        response = self.client.post(url, {"form_type": "nickname", "nickname": "ハナコ", "next": "/washoku/me/"})
        self.assertRedirects(response, "/washoku/me/", fetch_redirect_response=False)

    def test_outside_urls_are_ignored(self):

        page = self.client.get(reverse("portal:manage_apps") + "?next=https://example.com/")
        self.assertContains(page, "Yapp Portalへ戻る")
        self.assertNotContains(page, "example.com")
