import os
import tempfile
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path
from unittest import mock

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from outings.management.commands import outings_scheduler
from outings.models import (
    Event, EventCategory, EventHeart, EventLocation, EventOccurrence, EventSource,
    EventTag, EventfrogOccurrenceLink, OutingsPreference, TouristSpot,
)
from outings.services import ai_editor, schedule, weather
from outings.services.eventfrog_existing_sync import apply_cancellations
from outings.services.importer import import_items
from outings.services.selector import select
from outings.visitor import COOKIE_NAME


def iso(dt):
    return dt.isoformat()


def candidate(eid, *, start, end=None, title=None, region="ZH", score=75, participation="drop_in", category="music"):
    end = end or start + timedelta(hours=2)
    return {
        "id": eid, "group_id": "", "title": title or f"Konzert {eid}",
        "description": "Ein schönes Konzert für alle.", "start": iso(start), "end": iso(end),
        "url": f"https://eventfrog.ch/de/p/konzert-{eid}.html", "organizer": "Org",
        "image_url": "", "region": region, "city": "Zürich", "venue": f"Halle {eid}",
        "occurrences": [{"id": eid, "start": iso(start), "end": iso(end)}],
        "screen": {"score": score, "scores": {}, "participation": participation, "category": category, "language": "none"},
    }


def article(**overrides):
    data = {
        "title_ja": "秋のコンサート", "summary_ja": "地元の楽団が秋の名曲を演奏する、気軽に楽しめる夜のコンサートです。",
        "highlight_ja": "秋の名曲を生演奏で", "category": "music", "tags": ["family"],
        "language_barrier": "none", "is_free": True, "price_text": "", "age_note": "",
        "booking": "not_needed", "setting": "indoor", "version": ai_editor.ARTICLE_VERSION,
    }
    data.update(overrides)
    return data


def make_event(title="テスト", *, start, end=None, canton="ZH", city="Zürich", status=Event.Status.PUBLISHED,
               tier=Event.ListingTier.STANDARD, source=True, tags=("family",), **fields):
    location = EventLocation.objects.create(name="Halle", city=city, canton=canton)
    src = EventSource.objects.get_or_create(name="Eventfrog")[0] if source else None
    event = Event.objects.create(
        title=title, status=status, listing_tier=tier, location=location, source=src,
        external_id=f"x{Event.objects.count()}" if source else "", **fields,
    )
    for slug in tags:
        event.tags.add(EventTag.objects.get_or_create(slug=slug, defaults={"name": slug})[0])
    EventOccurrence.objects.create(event=event, start_at=start, end_at=end)
    return event


# =========================================================
# AI
# =========================================================

class AIEditorTests(TestCase):

    def test_screen_result_is_clamped_and_summed(self):
        result = ai_editor.clean_screen_result({
            "appeal": 50, "ease": 20, "fit": -3, "info": 10,
            "participation": "drop_in", "category": "nope", "language": "none",
        })
        self.assertEqual(result["score"], 35 + 20 + 0 + 10)
        self.assertEqual(result["category"], "other")

    def test_screen_batch_ignores_unknown_and_broken_items(self):
        events = [candidate("1", start=timezone.now() + timedelta(days=2)), candidate("2", start=timezone.now() + timedelta(days=3))]
        reply = {"results": [
            {"id": "1", "appeal": 30, "ease": 20, "fit": 20, "info": 10, "participation": "drop_in", "category": "music", "language": "none"},
            {"id": "2", "appeal": "high", "ease": 20, "fit": 20, "info": 10, "participation": "drop_in", "category": "music", "language": "none"},
            {"id": "999", "appeal": 30, "ease": 20, "fit": 20, "info": 10, "participation": "drop_in", "category": "music", "language": "none"},
        ]}
        with mock.patch.object(ai_editor, "_call", return_value=reply):
            results = ai_editor.screen_batch(events, model="m", key="k")
        self.assertEqual(set(results), {"1"})
        self.assertEqual(results["1"]["score"], 80)

    def test_article_drops_caveat_sentences(self):
        cleaned = ai_editor.clean_article(article(
            summary_ja="旧市街を夜警と一緒に歩き、街の伝説を聞くツアーです。英語対応は不明です。",
        ))
        self.assertNotIn("不明", cleaned["summary_ja"])
        self.assertIn("旧市街", cleaned["summary_ja"])

    def test_article_rejects_empty_summary(self):
        with self.assertRaises(ai_editor.AIError):
            ai_editor.clean_article(article(summary_ja="短い"))

    def test_schedule_digest_mentions_series_and_weekend(self):
        saturday = timezone.now() + timedelta(days=(5 - timezone.localdate().weekday()) % 7 or 7)
        event = {"occurrences": [
            {"start": iso(saturday + timedelta(days=7 * i)), "end": iso(saturday + timedelta(days=7 * i, hours=2))}
            for i in range(3)
        ]}
        digest = ai_editor.schedule_digest(event)
        self.assertIn("全3回", digest)
        self.assertIn("定期開催", digest)
        self.assertIn("週末", digest)


# =========================================================
# Selection and import
# =========================================================

class SelectorTests(TestCase):

    def test_courses_and_low_scores_are_left_out(self):
        now = timezone.now()
        picks = select([
            candidate("1", start=now + timedelta(days=2), score=85),
            candidate("2", start=now + timedelta(days=2), score=85, participation="series_course"),
            candidate("3", start=now + timedelta(days=2), score=50),
        ], target=10, now=now)
        self.assertEqual([p["id"] for p in picks], ["1"])
        self.assertEqual(picks[0]["listing_tier"], "featured")

    def test_running_exhibition_is_kept_but_never_featured(self):
        now = timezone.now()
        picks = select([candidate("1", start=now - timedelta(days=10), end=now + timedelta(days=30), score=90)], target=5, now=now)
        self.assertEqual(len(picks), 1)
        self.assertTrue(picks[0]["is_long_running"])
        self.assertEqual(picks[0]["listing_tier"], "standard")


class ImporterTests(TestCase):

    def test_invalid_row_does_not_block_others(self):
        now = timezone.now()
        good = {**candidate("100", start=now + timedelta(days=3)), "listing_tier": "standard", "article": article()}
        bad = {**candidate("200", start=now + timedelta(days=3)), "listing_tier": "standard", "article": article(),
               "url": "https://eventfrog.ch/de/p/other-999.html"}
        stats = import_items([bad, good], log=lambda *_: None, warn=lambda *_: None)
        self.assertEqual(stats["created"], 1)
        self.assertEqual(stats["invalid"], 1)
        event = Event.objects.get(external_id="100")
        self.assertTrue(event.is_free)
        self.assertEqual(event.highlight_ja, "秋の名曲を生演奏で")
        self.assertEqual(event.ai_score, 75)
        self.assertEqual(list(event.tags.values_list("slug", flat=True)), ["family"])

    def test_legacy_seed_format_still_imports(self):
        now = timezone.now()
        item = candidate("300", start=now + timedelta(days=3))
        item.pop("screen")
        item.update(listing_tier="compact", ai={"score": 70, "title_ja": "旧形式", "summary_ja": "旧形式の要約です。", "category": "art", "tags": [], "language_barrier": "none"})
        stats = import_items([item], log=lambda *_: None, warn=lambda *_: None)
        self.assertEqual(stats["created"], 1)

    def test_eventfrog_cancellation_marks_the_occurrence(self):
        now = timezone.now()
        import_items([{**candidate("400", start=now + timedelta(days=3)), "listing_tier": "standard", "article": article()}],
                     log=lambda *_: None, warn=lambda *_: None)
        stats = apply_cancellations({"400", "unknown"}, commit=True)
        self.assertEqual(stats["cancelled"], 1)
        self.assertTrue(EventfrogOccurrenceLink.objects.get(eventfrog_id="400").occurrence.is_cancelled)


class DailyRunTests(TestCase):

    def test_one_failed_article_is_skipped(self):
        now = timezone.now()
        raw = [{k: v for k, v in candidate(str(i), start=now + timedelta(days=i + 1)).items() if k != "screen"} for i in range(3)]

        def fake_screen(batch, **kwargs):
            return {str(e["id"]): {"score": 80, "scores": {}, "participation": "drop_in", "category": "music", "language": "none", "version": "t"} for e in batch}

        def fake_article(event, **kwargs):
            if event["id"] == "1":
                raise ai_editor.AIError("broken reply")
            return article(title_ja=f"記事{event['id']}")

        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch("outings.management.commands.daily_outings.data_dir", return_value=Path(tmp)), \
                mock.patch("outings.management.commands.daily_outings.collect_snapshot", return_value=(raw, set())), \
                mock.patch("outings.management.commands.daily_outings.enrich_locations", side_effect=lambda events, **kw: events), \
                mock.patch.object(ai_editor, "screen_batch", side_effect=fake_screen), \
                mock.patch.object(ai_editor, "write_article", side_effect=fake_article):
            call_command("daily_outings", commit=True, max_new=5, stdout=open(os.devnull, "w"), stderr=open(os.devnull, "w"))
        self.assertEqual(Event.objects.count(), 2)
        self.assertFalse(Event.objects.filter(external_id="1").exists())


class CleanupTests(TestCase):

    def test_past_events_are_deleted_and_just_ended_unpublished(self):
        now = timezone.now()
        old = make_event("old", start=now - timedelta(days=3), end=now - timedelta(days=2),
                         image_url="https://res.cloudinary.com/demo/image/upload/v12/yapp/outings/eventfrog/event-1.jpg")
        EventHeart.objects.create(event=old, visitor_id="00000000-0000-0000-0000-000000000001")
        just = make_event("just", start=now - timedelta(hours=5), end=now - timedelta(hours=3))
        member = make_event("member", start=now - timedelta(days=5), source=False)
        future = make_event("future", start=now + timedelta(days=2))
        with mock.patch("outings.management.commands.cleanup_outings.delete_photos", return_value=1) as photos:
            call_command("cleanup_outings", commit=True, stdout=open(os.devnull, "w"))
        photos.assert_called_once()
        self.assertEqual(set(Event.objects.values_list("title", flat=True)), {"just", "future"})
        self.assertFalse(EventHeart.objects.exists())
        just.refresh_from_db()
        future.refresh_from_db()
        self.assertEqual(just.status, Event.Status.CANCELLED)
        self.assertEqual(future.status, Event.Status.PUBLISHED)
        self.assertFalse(Event.objects.filter(pk=member.pk).exists())

    def test_cloudinary_public_id(self):
        from outings.management.commands.cleanup_outings import cloudinary_public_id
        self.assertEqual(cloudinary_public_id(
            "https://res.cloudinary.com/demo/image/upload/v12/yapp/outings/eventfrog/event-1.jpg", "demo"),
            "yapp/outings/eventfrog/event-1")
        self.assertIsNone(cloudinary_public_id("https://res.cloudinary.com/other/image/upload/v1/a.jpg", "demo"))
        self.assertIsNone(cloudinary_public_id("https://eventfrog.ch/a.jpg", "demo"))


class SchedulerTests(TestCase):

    def test_daily_run_uses_a_child_process(self):
        command = outings_scheduler.daily_command()
        self.assertEqual(command[3], "daily_outings")
        self.assertIn("--commit", command)
        self.assertEqual(command[command.index("--max-new") + 1], "15")

    def test_retries_after_failure_then_stops(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            now = datetime(2026, 10, 19, 1, 0, tzinfo=dt_timezone.utc)
            self.assertIsNone(outings_scheduler.next_attempt(state, now.replace(hour=0)))
            self.assertEqual(outings_scheduler.next_attempt(state, now), 1)
            marker = state / "2026-10-19.attempt-1"
            marker.write_text("x")
            os.utime(marker, (now.timestamp(), now.timestamp()))
            self.assertIsNone(outings_scheduler.next_attempt(state, now + timedelta(minutes=30)))
            self.assertEqual(outings_scheduler.next_attempt(state, now + timedelta(minutes=91)), 2)
            (state / "2026-10-19.success").write_text("ok")
            self.assertIsNone(outings_scheduler.next_attempt(state, now + timedelta(hours=5)))

    def test_late_start_still_runs_the_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            late = datetime(2026, 10, 19, 14, 0, tzinfo=dt_timezone.utc)
            self.assertEqual(outings_scheduler.next_attempt(Path(tmp), late), 1)


# =========================================================
# Pages
# =========================================================

@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class PageTestCase(TestCase):

    def setUp(self):
        self.now = timezone.now()
        # Never reach the weather API from tests.
        patcher = mock.patch("outings.services.weather.requests.get", side_effect=weather.requests.RequestException("offline"))
        patcher.start()
        self.addCleanup(patcher.stop)
        cache.clear()


class PageTests(PageTestCase):

    def test_preferences_keep_bern(self):
        self.client.post(reverse("outings:save_preferences"), {"regions": ["BE", "ZH", "XX"], "personalization": "on"})
        self.assertEqual(OutingsPreference.objects.get().favorite_regions, ["BE", "ZH"])

    def test_event_list_filters(self):
        make_event("チューリッヒの祭り", start=self.now + timedelta(days=2))
        make_event("ベルンの講演", start=self.now + timedelta(days=2), canton="BE", city="Bern")
        response = self.client.get(reverse("outings:event_home"), {"region": "BE"})
        self.assertContains(response, "ベルンの講演")
        self.assertNotContains(response, "チューリッヒの祭り")

    def test_event_list_shows_one_off_events_and_kids_tick_narrows(self):
        make_event("親子コンサート", start=self.now + timedelta(days=2))
        make_event("大人の講演", start=self.now + timedelta(days=2), tags=())
        weekly = make_event("毎週の教室", start=self.now + timedelta(days=1))
        for week in range(1, 4):
            EventOccurrence.objects.create(event=weekly, start_at=self.now + timedelta(days=1 + 7 * week))
        hand = make_event("図書館の読み聞かせ", start=self.now + timedelta(days=1), source=False)
        for week in range(1, 4):
            EventOccurrence.objects.create(event=hand, start_at=self.now + timedelta(days=1 + 7 * week))
        response = self.client.get(reverse("outings:event_home"), {"region": "all"})
        self.assertContains(response, "親子コンサート")
        self.assertContains(response, "図書館の読み聞かせ")
        self.assertContains(response, "大人の講演")
        self.assertNotContains(response, "毎週の教室")
        response = self.client.get(reverse("outings:event_home"), {"region": "all", "family": "1"})
        self.assertContains(response, "親子コンサート")
        self.assertNotContains(response, "大人の講演")
        # The tick is remembered on the next visit.
        response = self.client.get(reverse("outings:event_home"), {"region": "all"})
        self.assertNotContains(response, "大人の講演")

    def test_event_list_uses_favourite_regions_by_default(self):
        visitor = OutingsPreference.objects.create(favorite_regions=["BE"]).visitor_id
        make_event("チューリッヒの祭り", start=self.now + timedelta(days=2))
        make_event("ベルンの講演", start=self.now + timedelta(days=2), canton="BE", city="Bern")
        self.client.cookies[COOKIE_NAME] = str(visitor)
        response = self.client.get(reverse("outings:event_home"))
        self.assertContains(response, "ベルンの講演")
        self.assertNotContains(response, "チューリッヒの祭り")
        response = self.client.get(reverse("outings:event_home"), {"region": "all"})
        self.assertContains(response, "チューリッヒの祭り")

    def test_period_filter(self):
        make_event("明日のイベント", start=timezone.localtime(self.now).replace(hour=12, minute=0) + timedelta(days=1))
        make_event("来月のイベント", start=self.now + timedelta(days=20))
        response = self.client.get(reverse("outings:event_home"), {"when": "tomorrow"})
        self.assertContains(response, "明日のイベント")
        self.assertNotContains(response, "来月のイベント")

    def test_cancelled_and_past_events_are_hidden(self):
        event = make_event("中止のイベント", start=self.now + timedelta(days=2))
        event.occurrences.update(is_cancelled=True)
        make_event("終わったイベント", start=self.now - timedelta(days=2), end=self.now - timedelta(days=2) + timedelta(hours=2))
        response = self.client.get(reverse("outings:event_home"))
        self.assertNotContains(response, "中止のイベント")
        self.assertNotContains(response, "終わったイベント")

    def test_search_understands_other_spellings(self):
        make_event("音楽の夜", start=self.now + timedelta(days=2), city="Zürich")
        for query in ("Zurich", "チューリッヒ", "Zuerich"):
            self.assertContains(self.client.get(reverse("outings:search"), {"q": query}), "音楽の夜", msg_prefix=query)

    def test_detail_lists_only_upcoming_dates_and_offers_calendar(self):
        event = make_event("連続公演", start=self.now - timedelta(days=3), end=self.now - timedelta(days=3) + timedelta(hours=2))
        EventOccurrence.objects.create(event=event, start_at=self.now + timedelta(days=4))
        response = self.client.get(reverse("outings:event_detail", args=[event.pk]))
        self.assertEqual(len(response.context["date_rows"]), 1)
        ics = self.client.get(reverse("outings:event_calendar", args=[event.pk]))
        self.assertEqual(ics["Content-Type"], "text/calendar; charset=utf-8")
        self.assertIn(b"BEGIN:VEVENT", ics.content)

    def test_saved_ended_event_can_be_removed(self):
        event = make_event("終わったイベント", start=self.now + timedelta(days=1))
        visitor = OutingsPreference.objects.create().visitor_id
        EventHeart.objects.create(event=event, visitor_id=visitor)
        event.status = Event.Status.CANCELLED
        event.save()
        self.client.cookies[COOKIE_NAME] = str(visitor)
        response = self.client.get(reverse("outings:saved_all"))
        self.assertContains(response, "終了しました")
        self.assertNotContains(response, 'href="%s"' % reverse("outings:event_detail", args=[event.pk]))
        self.client.post(reverse("outings:toggle_heart", args=[event.pk]), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertFalse(EventHeart.objects.exists())

    def test_heart_toggle_returns_state(self):
        event = make_event("ハート", start=self.now + timedelta(days=1))
        response = self.client.post(reverse("outings:toggle_heart", args=[event.pk]), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.json(), {"hearted": True, "count": 1})

    def test_home_and_other_pages_render(self):
        make_event("ホーム", start=self.now + timedelta(days=1), tier=Event.ListingTier.FEATURED)
        for name in ("home", "event_home", "search", "saved_all", "my_page", "my_preferences"):
            self.assertEqual(self.client.get(reverse(f"outings:{name}")).status_code, 200, name)


    def test_about_shows_yapp_and_links_to_the_shared_support_page(self):
        response = self.client.get(reverse("outings:about_outings"))
        self.assertContains(response, 'id="support"')
        self.assertContains(response, reverse("portal:support") + "?from=outings")

    def test_shared_support_page_and_contact_form(self):
        from news.models import SupportRequest
        with self.settings(SWISS_NEWS_TWINT_URL="https://pay.example/twint"):
            response = self.client.get(reverse("portal:support"), {"from": "outings"})
        self.assertContains(response, "https://pay.example/twint")
        self.assertContains(response, "おでかけにもどる")
        self.assertContains(response, reverse("portal:support_contact", args=["bank"]) + "?from=outings")
        url = reverse("portal:support_contact", args=["bank"])
        response = self.client.post(url + "?from=outings", {"from": "outings", "bank_country": "ch", "email": "a@example.com"})
        self.assertRedirects(response, reverse("portal:support") + "?sent=1&from=outings", fetch_redirect_response=False)
        self.assertEqual(SupportRequest.objects.get().bank_country, "ch")
        self.assertEqual(self.client.get(reverse("portal:support_contact", args=["nope"])).status_code, 302)

    def test_support_page_shows_the_twint_phone_only_when_set(self):
        self.assertNotContains(self.client.get(reverse("portal:support")), "TWINTで送金")
        with self.settings(YAPP_TWINT_PHONE="+41 79 000 00 00"):
            response = self.client.get(reverse("portal:support"))
        self.assertContains(response, "TWINTで送金")
        self.assertContains(response, "+41 79 000 00 00")

    def test_home_shows_weekend_family_events_and_spots(self):
        from outings.models import FamilySpot
        from outings.services import weather as wx
        saturday = wx.weekend_days(self.now)[-1]
        start = timezone.make_aware(datetime.combine(saturday, datetime.min.time())) + timedelta(hours=14)
        make_event("週末の親子会", start=start)
        make_event("週末の大人会", start=start, tags=())
        FamilySpot.objects.all().delete()
        FamilySpot.objects.create(name="Open Park", summary_ja="公園", status="published")
        html = self.client.get(reverse("outings:home")).content.decode()
        self.assertIn("今週末どこ行く", html)
        self.assertIn("週末の親子会", html)
        self.assertNotIn("週末の大人会", html)
        self.assertIn("Open Park", html)


class FeedbackTests(PageTestCase):

    def test_feedback_is_saved_once_per_minute_and_bots_are_ignored(self):
        from outings.models import OutingsFeedback
        url = reverse("outings:about_outings")
        response = self.client.post(url, {"message": "地図があるとうれしいです"})
        self.assertRedirects(response, url + "?sent=1#feedback", fetch_redirect_response=False)
        self.assertEqual(OutingsFeedback.objects.get().message, "地図があるとうれしいです")
        response = self.client.post(url, {"message": "もう一通"})
        self.assertRedirects(response, url + "?sent=wait#feedback", fetch_redirect_response=False)
        self.assertEqual(OutingsFeedback.objects.count(), 1)
        other = self.client_class()
        other.post(url, {"message": "spam", "website": "http://spam.example"})
        self.assertEqual(OutingsFeedback.objects.count(), 1)
        self.assertContains(self.client.get(url + "?sent=1"), "送信しました")

    def test_yapp_home_teases_outings_instead_of_the_travel_app(self):
        response = self.client.get(reverse("portal:home"))
        self.assertContains(response, "おでかけ")
        self.assertNotContains(response, "旅トモ")
        self.assertNotContains(response, 'href="%s"' % reverse("outings:home"))


class SearchTests(PageTestCase):
    """Search page: every word must match, ranked by where it matched."""

    def search(self, **params):
        return self.client.get(reverse("outings:search"), params)

    def test_all_words_must_match_and_synonyms_count(self):
        make_event("バーゼルのジャズ", start=self.now + timedelta(days=2), canton="BS", city="Basel")
        make_event("チューリッヒのジャズ", start=self.now + timedelta(days=2))
        response = self.search(q="Basel jazz")
        self.assertContains(response, "バーゼルのジャズ")
        self.assertNotContains(response, "チューリッヒのジャズ")
        # A German word finds the Japanese one; hiragana finds katakana.
        make_event("夜のコンサート", start=self.now + timedelta(days=2))
        self.assertContains(self.search(q="Konzert"), "夜のコンサート")
        make_event("こどもの工作", start=self.now + timedelta(days=2))
        self.assertContains(self.search(q="コドモ"), "こどもの工作")

    def test_title_match_ranks_above_description_match(self):
        make_event("市場の話", start=self.now + timedelta(days=1), summary_ja="クリスマスの話もします")
        make_event("クリスマスマーケット", start=self.now + timedelta(days=5))
        html = self.search(q="クリスマス").content.decode()
        self.assertLess(html.index("クリスマスマーケット"), html.index("市場の話"))
        html = self.search(q="クリスマス", sort="date").content.decode()
        self.assertLess(html.index("市場の話"), html.index("クリスマスマーケット"))

    def test_partial_match_when_no_event_has_every_word(self):
        make_event("ベルンの朝市", start=self.now + timedelta(days=2), canton="BE", city="Bern")
        response = self.search(q="Bern 花火")
        self.assertContains(response, "ベルンの朝市")
        self.assertContains(response, "一部の言葉に一致")

    def test_no_results_suggests_which_condition_to_drop(self):
        make_event("有料の公演", start=self.now + timedelta(days=2))
        response = self.search(free="1")
        self.assertContains(response, "見つかりませんでした")
        self.assertContains(response, "無料を外す")

    def test_next_weekend_and_regions(self):
        today = timezone.localdate(self.now)
        saturday = today + timedelta(days=(5 - today.weekday()) % 7 or 7)
        if today.weekday() == 6:
            saturday = today + timedelta(days=6)
        noon = timezone.make_aware(datetime.combine(saturday + timedelta(days=7), datetime.min.time())) + timedelta(hours=12)
        make_event("来週末の祭り", start=noon, canton="BE", city="Bern")
        make_event("明日の講演", start=self.now + timedelta(days=1))
        response = self.search(when="next_weekend")
        self.assertContains(response, "来週末の祭り")
        self.assertNotContains(response, "明日の講演")
        response = self.search(region=["BE", "ZH"])
        self.assertContains(response, "来週末の祭り")
        self.assertContains(response, "明日の講演")

    def test_sunny_sort_puts_sunny_places_first(self):
        from outings import sunny
        day = timezone.localdate(self.now) + timedelta(days=1)
        start = timezone.make_aware(datetime.combine(day, datetime.min.time())) + timedelta(hours=12)
        wet = make_event("雨の町の会", start=start)
        dry = make_event("晴れの町の会", start=start + timedelta(hours=1))
        for event, (lat, lon) in ((wet, sunny.POINTS[0]), (dry, sunny.POINTS[-1])):
            event.location.latitude, event.location.longitude = lat, lon
            event.location.save()
        forecasts = {sunny.POINTS[0]: {day.isoformat(): {"code": 61, "rain": 80}},
                     sunny.POINTS[-1]: {day.isoformat(): {"code": 0, "rain": 0}}}
        with mock.patch.object(sunny.weather, "_forecasts", return_value=forecasts):
            body = self.search(sort="sunny").content.decode()
        self.assertLess(body.index("晴れの町の会"), body.index("雨の町の会"))
        self.assertIn("晴れ優先", body)

    def test_keyword_also_finds_trips(self):
        from outings.models import TouristSpot
        TouristSpot.objects.create(
            external_id="t1", spot_type=TouristSpot.SpotType.DESTINATION, title_original="Arosa",
            title_ja="アローザ", summary_ja="山あいのリゾート", official_url="https://example.com",
            status=TouristSpot.Status.PUBLISHED,
        )
        response = self.search(q="あろーざ")
        self.assertContains(response, "旅行先")
        self.assertContains(response, "アローザ")

    def test_old_family_parameter_still_works(self):
        make_event("親子の会", start=self.now + timedelta(days=2), tags=["family"])
        make_event("大人の会", start=self.now + timedelta(days=2), tags=())
        response = self.search(tag="family")
        self.assertContains(response, "親子の会")
        self.assertNotContains(response, "大人の会")


class NavigationTests(PageTestCase):

    def test_search_is_in_the_phone_tab_bar_and_marked_active(self):
        html = self.client.get(reverse("outings:search")).content.decode()
        tabbar = html[html.index('class="outings-bottom-nav tabbar"'):]
        self.assertIn("tabbar__search active", tabbar)
        # The events tab is no longer highlighted on the search page.
        self.assertIn('href="%s" class=""' % reverse("outings:event_home"), tabbar)


class ScheduleLabelTests(TestCase):

    def test_ongoing_label(self):
        now = timezone.now()
        occurrence = EventOccurrence(start_at=now - timedelta(days=5), end_at=now + timedelta(days=10))
        self.assertTrue(schedule.occurrence_label(occurrence, now).startswith("開催中"))

    def test_midnight_start_has_no_time(self):
        start = timezone.make_aware(datetime(2026, 11, 7, 0, 0))
        label = schedule.occurrence_label(EventOccurrence(start_at=start, end_at=None), start - timedelta(days=1))
        self.assertEqual(label, "11/7（土）")


class FakeResponse:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


class WeatherTests(TestCase):

    def setUp(self):
        cache.clear()

    def test_attaches_forecast_for_the_event_day(self):
        now = timezone.now()
        event = make_event("屋外フェス", start=now + timedelta(days=2), city="Bern", canton="BE")
        event.next_occurrence = event.occurrences.get()
        day = timezone.localdate(event.next_occurrence.start_at).isoformat()
        responses = {
            weather.GEOCODE_URL: {"results": [
                {"country_code": "CH", "admin1": "Bern", "latitude": 46.948, "longitude": 7.447},
            ]},
            weather.FORECAST_URL: {"daily": {
                "time": [day], "weather_code": [61], "temperature_2m_max": [14.4],
                "temperature_2m_min": [6.2], "precipitation_probability_max": [70],
            }},
        }
        with mock.patch("outings.services.weather.requests.get", side_effect=lambda url, **kw: FakeResponse(responses[url])) as get:
            weather.attach([event], now)
            self.assertEqual(event.weather, {"emoji": "🌧️", "label": "小雨", "temp": "14° / 6°", "rain": "70%"})
            # Coordinates are stored and the forecast is cached.
            event.location.refresh_from_db()
            self.assertIsNotNone(event.location.latitude)
            weather.attach([event], now)
            self.assertEqual(get.call_count, 2)

    def test_far_future_and_failures_show_nothing(self):
        now = timezone.now()
        far = make_event("来月", start=now + timedelta(days=20))
        far.next_occurrence = far.occurrences.get()
        soon = make_event("明日", start=now + timedelta(days=1))
        soon.next_occurrence = soon.occurrences.get()
        with mock.patch("outings.services.weather.requests.get", side_effect=weather.requests.RequestException("down")):
            weather.attach([far, soon], now)
        self.assertIsNone(far.weather)
        self.assertIsNone(soon.weather)

    def test_weekend_weather_for_trips(self):
        from types import SimpleNamespace
        # Wednesday: this weekend is Saturday and Sunday.
        wednesday = timezone.make_aware(datetime(2026, 10, 21, 12, 0))
        self.assertEqual([d.isoformat() for d in weather.weekend_days(wednesday)], ["2026-10-24", "2026-10-25"])
        sunday = timezone.make_aware(datetime(2026, 10, 25, 9, 0))
        self.assertEqual([d.isoformat() for d in weather.weekend_days(sunday)], ["2026-10-25"])
        spot = SimpleNamespace(latitude=46.8, longitude=9.7)
        no_coords = SimpleNamespace(latitude=None, longitude=None)
        forecast = {"daily": {
            "time": ["2026-10-24", "2026-10-25"], "weather_code": [0, 71],
            "temperature_2m_max": [12, 3], "temperature_2m_min": [2, -4],
            "precipitation_probability_max": [0, 80],
        }}
        with mock.patch("outings.services.weather.requests.get", return_value=FakeResponse(forecast)):
            weather.attach_weekend([spot, no_coords], wednesday)
        self.assertEqual([(d["day"], d["emoji"], d["temp"]) for d in spot.weekend_weather],
                         [("土", "☀️", "12° / 2°"), ("日", "🌨️", "3° / -4°")])
        self.assertIsNone(no_coords.weekend_weather)


def commons_page(title, lat=None, lon=None, width=1200, author="Jane", license_name="CC BY-SA 4.0"):
    page = {
        "title": title,
        "imageinfo": [{
            "mime": "image/jpeg",
            "url": f"https://upload.wikimedia.org/{title}",
            "thumburl": f"https://upload.wikimedia.org/thumb/{title}",
            "descriptionurl": f"https://commons.wikimedia.org/wiki/{title}",
            "width": width,
            "height": 800,
            "extmetadata": {
                "LicenseShortName": {"value": license_name},
                "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0"},
                "Artist": {"value": author},
                "ImageDescription": {"value": ""},
            },
        }],
    }
    if lat is not None:
        page["coordinates"] = [{"lat": lat, "lon": lon}]
    return page


class FakeCommons:
    """Answers the name search and the nearby search with fixed pages."""

    def __init__(self, by_name, nearby):
        self.by_name, self.nearby = by_name, nearby
        self.headers = {}

    def get(self, url, params, timeout):
        pages = self.nearby if params.get("generator") == "geosearch" else self.by_name
        return FakeResponse({"query": {"pages": pages}})


class TripPhotoTests(TestCase):
    def make_spot(self, title, **extra):
        return TouristSpot.objects.create(
            external_id=title, spot_type=TouristSpot.SpotType.ATTRACTION, title_original=title,
            official_url="https://example.com", status=TouristSpot.Status.PUBLISHED, **extra,
        )

    def run_command(self, commons, *args):
        with mock.patch("outings.management.commands.auto_assign_tourist_images.requests.Session", return_value=commons), \
                mock.patch("outings.management.commands.auto_assign_tourist_images.time.sleep"):
            call_command("auto_assign_tourist_images", "--commit", *args, stdout=open(os.devnull, "w"))

    def test_name_match_is_used_first(self):
        spot = self.make_spot("Rheinfall", latitude=47.677, longitude=8.615)
        self.run_command(FakeCommons([commons_page("File:Rheinfall bei Schaffhausen.jpg")], []))
        spot.refresh_from_db()
        self.assertEqual(spot.details["approved_image"]["match"], "name")

    def test_closest_geotagged_photo_when_the_name_finds_nothing(self):
        spot = self.make_spot("Erlebniswelt Muottas Muragl", latitude=46.5, longitude=9.9)
        nearby = [
            commons_page("File:Far view.jpg", lat=46.507, lon=9.9),
            commons_page("File:Wanderkarte Engadin.jpg", lat=46.5, lon=9.9),
            commons_page("File:Tiny.jpg", lat=46.5, lon=9.9, width=300),
            commons_page("File:Near view.jpg", lat=46.501, lon=9.9),
        ]
        self.run_command(FakeCommons([commons_page("File:Something else.jpg")], nearby))
        spot.refresh_from_db()
        image = spot.details["approved_image"]
        self.assertEqual(image["file_title"], "File:Near view.jpg")
        self.assertEqual(image["match"], "nearby")

    def test_retry_searches_spots_checked_before(self):
        spot = self.make_spot("Zug", latitude=47.17, longitude=8.51, details={"commons_search_checked": True})
        commons = FakeCommons([commons_page("File:Zug Altstadt.jpg")], [])
        self.run_command(commons)
        spot.refresh_from_db()
        self.assertNotIn("approved_image", spot.details)
        self.run_command(commons, "--retry")
        spot.refresh_from_db()
        self.assertEqual(spot.details["approved_image"]["file_title"], "File:Zug Altstadt.jpg")


class PublicUserAccessTests(PageTestCase):
    def test_signed_up_public_users_can_open_outings(self):
        from django.contrib.auth.models import Group, User
        user = User.objects.create_user("friend", password="pw-12345")
        user.groups.add(Group.objects.get_or_create(name="public_users")[0])
        self.client.force_login(user)
        for name in ("outings:home", "outings:search", "outings:about_outings"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)


class FamilySpotTests(PageTestCase):

    def make(self, name, **fields):
        from outings.models import FamilySpot
        defaults = dict(kind=FamilySpot.Kind.PARK, canton="ZH", town="Zürich", status=FamilySpot.Status.PUBLISHED)
        defaults.update(fields)
        return FamilySpot.objects.create(name=name, **defaults)

    def setUp(self):
        super().setUp()
        from outings.models import FamilySpot
        FamilySpot.objects.all().delete()  # drop the seeded spots
        self.park = self.make("Sunny Park", name_ja="ひなた公園", price=FamilySpot.Price.FREE)
        self.museum = self.make("Rain Museum", kind=FamilySpot.Kind.MUSEUM, canton="BE", rainy_ok=True,
                                price=FamilySpot.Price.PAID, language="helps", age_min=6, age_max=12,
                                trip=FamilySpot.Trip.OVERNIGHT)
        self.draft = self.make("Secret Draft", status=FamilySpot.Status.DRAFT)

    def names(self, query=""):
        query = "?kids=1" + ("&" + query.lstrip("?") if query else "")
        response = self.client.get(reverse("outings:tourist_spot_list") + query)
        self.assertEqual(response.status_code, 200)
        return sorted(spot.name for spot in response.context["spots"])

    def test_list_shows_published_only_and_filters(self):
        self.assertEqual(self.names(), ["Rain Museum", "Sunny Park"])
        self.assertEqual(self.names("?rainy=1"), ["Rain Museum"])
        self.assertEqual(self.names("?free=1"), ["Sunny Park"])
        self.assertEqual(self.names("?easy=1"), ["Sunny Park"])
        self.assertEqual(self.names("?kind=museum"), ["Rain Museum"])
        self.assertEqual(self.names("?area=bern"), ["Rain Museum"])
        self.assertEqual(self.names("?age=0"), ["Sunny Park"])
        self.assertEqual(self.names("?age=6"), ["Rain Museum", "Sunny Park"])
        self.assertEqual(self.names("?trip=day"), ["Sunny Park"])
        self.assertEqual(self.names("?trip=overnight"), ["Rain Museum"])
        self.assertEqual(self.names("?kind=bogus"), self.names())

    def test_profile_card_asks_once_and_tailors_home(self):
        from outings.models import FamilySpot, OutingsPreference
        self.make("Bern Park", canton="BE", age_min=0, age_max=3)
        home = self.client.get(reverse("outings:home"))
        self.assertContains(home, "あなたに合わせる")
        response = self.client.post(reverse("outings:profile_save"), {
            "areas": ["bern", "bogus"], "german": "none", "kids": "yes", "ages": ["0"],
            "days_off": "weekend", "next": "/outings/",
        })
        self.assertRedirects(response, "/outings/", fetch_redirect_response=False)
        preference = OutingsPreference.objects.get()
        self.assertEqual(preference.areas, ["bern"])
        self.assertEqual(preference.kid_ages, ["0"])
        self.assertIn("BE", preference.favorite_regions)
        home = self.client.get(reverse("outings:home"))
        self.assertNotContains(home, 'id="og-ask-title"')
        self.assertEqual(home.context["weekend_spots"][0].name, "Bern Park")
        # The 子連れ tick follows the answer.
        trips = self.client.get(reverse("outings:tourist_spot_list"))
        self.assertIn("spots", trips.context)
        self.assertEqual(FamilySpot.objects.count(), 4)

    def test_profile_skip_and_weekday(self):
        from outings.models import OutingsPreference
        self.client.post(reverse("outings:profile_save"), {"skip": "1"})
        self.assertEqual(OutingsPreference.objects.get().setup, "skipped")
        self.assertNotContains(self.client.get(reverse("outings:home")), 'id="og-ask-title"')
        self.client.post(reverse("outings:profile_save"), {"kids": "no", "days_off": "weekday"})
        home = self.client.get(reverse("outings:home"))
        self.assertContains(home, "平日のおすすめ")
        self.assertNotIn("spots", self.client.get(reverse("outings:tourist_spot_list")).context)
        page = self.client.get(reverse("outings:my_preferences"))
        self.assertContains(page, 'value="weekday" checked')

    def test_sunny_page_puts_sunny_places_first(self):
        from outings import sunny
        from outings.models import FamilySpot
        FamilySpot.objects.filter(pk=self.park.pk).update(latitude=47.37, longitude=8.54)    # Zurich
        FamilySpot.objects.filter(pk=self.museum.pk).update(latitude=46.0, longitude=8.95,   # Lugano
                                                              season=FamilySpot.Season.YEAR)
        today = timezone.localdate().isoformat()

        def forecasts(points):
            # Rain in Zurich, sun in Lugano.
            return {p: {today: {"code": 0 if p == (46.0, 8.95) else 63, "max": 15, "min": 5, "rain": 10 if p == (46.0, 8.95) else 90}}
                    for p in points}

        with mock.patch.object(sunny.weather, "_forecasts", side_effect=forecasts), \
                mock.patch.object(sunny, "locate", return_value=None):
            response = self.client.get(reverse("outings:sunny"), {"what": "kids", "day": today})
        self.assertEqual(response.status_code, 200)
        groups = {g["key"]: [i["title"] for i in g["rows"]] for g in response.context["groups"]}
        self.assertEqual(groups["sunny"], ["Rain Museum"])
        self.assertEqual(groups["wet"], ["ひなた公園"])
        self.assertIn("ルガーノ", response.context["sunny_areas"])
        self.assertContains(response, "og-map-data")
        for name in ("outings:event_home", "outings:tourist_spot_list"):
            self.assertContains(self.client.get(reverse(name)), "晴れの場所をさがす")

    def test_season(self):
        from outings.models import FamilySpot
        spot = FamilySpot(season=FamilySpot.Season.WARM)
        self.assertTrue(spot.open_in(7))
        self.assertFalse(spot.open_in(1))

    def test_detail_has_map_link_and_hides_drafts(self):
        response = self.client.get(reverse("outings:spot_detail", args=[self.park.pk]))
        self.assertContains(response, "ひなた公園")
        self.assertContains(response, "Googleマップで開く")
        self.assertContains(response, "https://www.google.com/maps/search/")
        self.assertEqual(self.client.get(reverse("outings:spot_detail", args=[self.draft.pk])).status_code, 404)

    def test_home_and_trips_link_to_spots(self):
        home = self.client.get(reverse("outings:home"))
        self.assertContains(home, reverse("outings:spot_detail", args=[self.park.pk]))
        self.assertNotContains(home, "Secret Draft")
        trips = self.client.get(reverse("outings:tourist_spot_list"))
        self.assertContains(trips, "?kids=1")
        old = self.client.get(reverse("outings:spot_list") + "?rainy=1")
        self.assertRedirects(old, reverse("outings:tourist_spot_list") + "?rainy=1&kids=1", fetch_redirect_response=False)

    def test_kids_tick_is_remembered(self):
        url = reverse("outings:tourist_spot_list")
        self.client.get(url + "?kids=1")
        self.assertIn("spots", self.client.get(url).context)
        self.client.get(url + "?kids=0")
        self.assertNotIn("spots", self.client.get(url).context)

    def test_seed_spots_exist(self):
        from importlib import import_module
        from django.apps import apps as django_apps
        from outings.models import FamilySpot
        import_module("outings.migrations.0018_family_spot_seed").add_spots(django_apps, None)
        self.assertTrue(FamilySpot.objects.filter(name="Park im Grüene", status="published").exists())


class TripImportTests(TestCase):

    def test_rate_limit_waits_and_retries(self):
        from outings.services.myswitzerland import _get_with_backoff

        class Reply:
            def __init__(self, status):
                self.status_code, self.headers = status, {}

        replies = [Reply(429), Reply(429), Reply(200)]
        waits = []

        class Session:
            def get(self, url, params, timeout):
                return replies.pop(0)

        with self.settings():
            import contextlib, io
            with contextlib.redirect_stdout(io.StringIO()):
                response = _get_with_backoff(Session(), "u", {}, sleep=waits.append)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(waits, [20, 40])


    def item(self, identifier, name):
        return {"identifier": identifier, "name": name, "url": f"https://www.myswitzerland.com/de/{identifier}/",
                "abstract": "Kurz", "description": "Lang", "geo": {"latitude": 47.0, "longitude": 8.0}}

    def test_new_spots_wait_hidden_and_existing_keep_status(self):
        hidden = TouristSpot.objects.create(
            external_id="old", spot_type="attractions", title_original="Old", official_url="https://www.myswitzerland.com/de/old/",
            status=TouristSpot.Status.HIDDEN,
        )
        pages = [[self.item("new", "Neu"), self.item("old", "Old renamed")]]
        with mock.patch("outings.management.commands.import_myswitzerland.iter_spot_pages", return_value=iter(pages)):
            call_command("import_myswitzerland", "--type", "attractions", "--all", "--commit", stdout=open(os.devnull, "w"))
        self.assertEqual(TouristSpot.objects.get(external_id="new").status, TouristSpot.Status.PENDING)
        hidden.refresh_from_db()
        self.assertEqual(hidden.status, TouristSpot.Status.HIDDEN)
        self.assertEqual(hidden.title_original, "Old renamed")

    def test_dry_run_saves_nothing(self):
        with mock.patch("outings.management.commands.import_myswitzerland.iter_spot_pages", return_value=iter([[self.item("a", "A")]])):
            call_command("import_myswitzerland", "--type", "attractions", "--all", stdout=open(os.devnull, "w"))
        self.assertFalse(TouristSpot.objects.exists())

    @mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test"})
    def test_enrichment_publishes_waiting_spots(self):
        from outings.management.commands import enrich_tourist_spots as enrich
        spot = TouristSpot.objects.create(
            external_id="w", spot_type="attractions", title_original="Rheinfall",
            official_url="https://www.myswitzerland.com/de/w/", status=TouristSpot.Status.PENDING,
        )
        hidden = TouristSpot.objects.create(
            external_id="h", spot_type="attractions", title_original="Hidden",
            official_url="https://www.myswitzerland.com/de/h/", status=TouristSpot.Status.HIDDEN,
        )

        def fake(api_key, model, prompt, data, schema):
            enrich.USAGE["input"] += 1000
            ids = [record["id"] for record in data["spots"]]
            if prompt == enrich.TRANSLATION_PROMPT:
                return {"results": [{"id": i, "japanese_subtitle": "ライン滝", "summary_ja": "大きな滝。",
                                     "highlights_ja": ["滝の近くまで船で行ける"], "guide_ja": "ヨーロッパ最大級の滝。"} for i in ids]}
            return {"results": [{"id": i, "reason": "迫力", **{k: 5 for k in enrich.SCORE_FIELDS}} for i in ids]}

        with mock.patch.object(enrich, "call_openai", side_effect=fake):
            call_command("enrich_tourist_spots", "--limit", "10", "--commit", stdout=open(os.devnull, "w"))
        spot.refresh_from_db()
        hidden.refresh_from_db()
        self.assertEqual(spot.status, TouristSpot.Status.PUBLISHED)
        self.assertEqual(spot.summary_ja, "大きな滝。")
        self.assertEqual(spot.details["highlights_ja"], ["滝の近くまで船で行ける"])
        self.assertIsNone(hidden.ai_reviewed_at)
        page = self.client.get(reverse("outings:tourist_spot_detail", args=[spot.pk]))
        self.assertContains(page, "ヨーロッパ最大級の滝。")
        # Older spots without the guide can be rewritten once.
        from outings.management.commands.enrich_tourist_spots import choose_spots
        self.assertEqual(choose_spots(10, False, missing_guide=True), [])

    @mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test"})
    def test_enrichment_survives_repeated_and_missing_ai_ids(self):
        from outings.management.commands import enrich_tourist_spots as enrich
        spots = [TouristSpot.objects.create(
            external_id=f"d{n}", spot_type="attractions", title_original=f"Spot {n}",
            official_url=f"https://www.myswitzerland.com/de/d{n}/", status=TouristSpot.Status.PENDING,
        ) for n in range(3)]
        first, second, third = (s.pk for s in spots)

        def fake(api_key, model, prompt, data, schema):
            if prompt == enrich.TRANSLATION_PROMPT:
                # Repeats the first ID and forgets the third.
                return {"results": [{"id": i, "japanese_subtitle": "x", "summary_ja": "説明"} for i in (first, first, second)]}
            return {"results": [{"id": i, "reason": "r", **{k: 1 for k in enrich.SCORE_FIELDS}} for i in (first, second, 999)]}

        with mock.patch.object(enrich, "call_openai", side_effect=fake):
            call_command("enrich_tourist_spots", "--limit", "10", "--commit", stdout=open(os.devnull, "w"))
        statuses = [TouristSpot.objects.get(pk=pk).status for pk in (first, second, third)]
        self.assertEqual(statuses, [TouristSpot.Status.PUBLISHED, TouristSpot.Status.PUBLISHED, TouristSpot.Status.PENDING])

    def test_hand_written_introductions_round_trip(self):
        import csv, tempfile
        spot = TouristSpot.objects.create(
            external_id="ext-1", spot_type="attractions", title_original="Aareschlucht", summary_ja="AIの文",
            official_url="https://www.myswitzerland.com/de/a/", status=TouristSpot.Status.PENDING,
        )
        path = tempfile.mktemp(suffix=".csv")
        call_command("export_tourist_texts", path, "--all", stdout=open(os.devnull, "w"))
        with open(path, encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(rows[0]["external_id"], "ext-1")
        rows[0]["私の紹介文"] = "岩の間を歩く峡谷。\n夏も涼しい。"
        rows.append({**rows[0], "external_id": "nope", "名前": "Unknown"})
        with open(path, "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        call_command("import_tourist_texts", path, stdout=open(os.devnull, "w"))
        spot.refresh_from_db()
        self.assertEqual(spot.intro_ja, "")  # check only
        call_command("import_tourist_texts", path, "--commit", stdout=open(os.devnull, "w"))
        spot.refresh_from_db()
        self.assertEqual(spot.intro_ja, "岩の間を歩く峡谷。\n夏も涼しい。")
        self.assertEqual(spot.status, TouristSpot.Status.PUBLISHED)
        page = self.client.get(reverse("outings:tourist_spot_detail", args=[spot.pk]))
        self.assertContains(page, "夏も涼しい。")
        self.assertNotContains(page, "AIの文")

    def test_intros_file_fills_matching_spots(self):
        import json
        from outings.management.commands import apply_tourist_intros as apply
        self.assertGreaterEqual(len(apply.load_intros()), 50)  # the shipped file parses
        spot = TouristSpot.objects.create(
            external_id="e1", spot_type="attractions", title_original='Detektiv-Trail Bern "Detektiv Dachs"',
            official_url="https://www.myswitzerland.com/de/e1/", status=TouristSpot.Status.PENDING,
        )
        edited = TouristSpot.objects.create(
            external_id="e2", spot_type="tours", title_original="Gürbe–Sense, Etappe 1/2", intro_ja="管理画面で直した",
            official_url="https://www.myswitzerland.com/de/e2/", status=TouristSpot.Status.PUBLISHED,
        )
        data = {"Detektiv-Trail Bern “Detektiv Dachs”": "探偵の道。", "Gürbe-Sense, Etappe 1/2": "自転車の道。"}
        path = Path(tempfile.mkdtemp()) / "intros.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        with mock.patch.object(apply, "DATA", path):
            call_command("apply_tourist_intros", stdout=open(os.devnull, "w"))
        spot.refresh_from_db()
        edited.refresh_from_db()
        self.assertEqual((spot.intro_ja, spot.status), ("探偵の道。", TouristSpot.Status.PUBLISHED))
        self.assertEqual(edited.intro_ja, "管理画面で直した")

    def test_unverified_spots_are_hidden_until_they_have_an_intro(self):
        from outings.management.commands import apply_tourist_intros as apply
        self.assertIn(apply.normalize("Sagenwege"), apply.load_unverified())  # the shipped list parses
        bare = TouristSpot.objects.create(
            external_id="u1", spot_type="tours", title_original="Sagenwege",
            official_url="https://www.myswitzerland.com/de/u1/", status=TouristSpot.Status.PUBLISHED,
        )
        written = TouristSpot.objects.create(
            external_id="u2", spot_type="tours", title_original="Moorweg", intro_ja="自分で書いた",
            official_url="https://www.myswitzerland.com/de/u2/", status=TouristSpot.Status.PUBLISHED,
        )
        call_command("apply_tourist_intros", stdout=open(os.devnull, "w"))
        bare.refresh_from_db()
        written.refresh_from_db()
        self.assertEqual(bare.status, TouristSpot.Status.HIDDEN)
        self.assertEqual(written.status, TouristSpot.Status.PUBLISHED)

    def test_family_intros_fill_spots_and_show_on_the_page(self):
        from outings.models import FamilySpot
        spot = FamilySpot.objects.get(name="Park im Grüene")
        FamilySpot.objects.filter(pk=spot.pk).update(intro_ja="")
        call_command("apply_family_intros", stdout=open(os.devnull, "w"))
        spot.refresh_from_db()
        self.assertIn("ロバ", spot.intro_ja)
        self.assertContains(self.client.get(reverse("outings:spot_detail", args=[spot.pk])), "ロバ")

    def test_markdown_intro_batches_parse(self):
        from outings.management.commands.merge_tourist_intros_md import parse
        text = """# 第2弾
## 51〜60件
### 51. Alpenpässe-Weg, Etappe 4/43
散策・ハイキング｜グラウビュンデン州
峠を越える長い道。
[image](https://www.google.com/s2/favicons?domain=https://schweizmobil.ch)
SchweizMobil
52. Bierhübeli
体験・ツアー｜ベルン
ライブハウス。
Bierhübeli+1
52. Bierhübeli（公式情報に基づく確定版）
体験・ツアー｜ベルン
ベルンのライブハウス。
以上で第2弾の50件が完成。
次の対象：101〜150件
"""
        self.assertEqual(parse(text), {"Alpenpässe-Weg, Etappe 4/43": "峠を越える長い道。", "Bierhübeli": "ベルンのライブハウス。"})

    def test_nightly_trip_text_is_off_unless_turned_on(self):
        with mock.patch.dict(os.environ, {"OUTINGS_TRIP_AI_PER_NIGHT": ""}):
            self.assertNotIn("--trip-ai", outings_scheduler.daily_command())
        with mock.patch.dict(os.environ, {"OUTINGS_TRIP_AI_PER_NIGHT": "250"}):
            command = outings_scheduler.daily_command()
        self.assertEqual(command[command.index("--trip-ai") + 1], "250")

    def test_max_new_shares_the_limit_between_types(self):
        def pages(spot_type, **kwargs):
            return iter([[self.item(f"{spot_type}-{n}", f"{spot_type} {n}") for n in range(5)]])
        with mock.patch("outings.management.commands.import_myswitzerland.iter_spot_pages", side_effect=pages):
            call_command("import_myswitzerland", "--all", "--max-new", "6", "--commit", stdout=open(os.devnull, "w"))
        counts = {t: TouristSpot.objects.filter(spot_type=t).count() for t in ("attractions", "tours", "destinations", "offers")}
        self.assertEqual(sum(counts.values()), 6)
        self.assertTrue(all(counts.values()), counts)
