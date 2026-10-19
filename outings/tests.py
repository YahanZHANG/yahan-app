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
               tier=Event.ListingTier.STANDARD, source=True, tags=(), **fields):
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


class SchedulerTests(TestCase):

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
        make_event("チューリッヒの祭り", start=self.now + timedelta(days=2), tags=["family"])
        make_event("ベルンの講演", start=self.now + timedelta(days=2), canton="BE", city="Bern")
        response = self.client.get(reverse("outings:event_home"), {"region": "BE"})
        self.assertContains(response, "ベルンの講演")
        self.assertNotContains(response, "チューリッヒの祭り")
        response = self.client.get(reverse("outings:event_home"), {"family": "1"})
        self.assertContains(response, "チューリッヒの祭り")
        self.assertNotContains(response, "ベルンの講演")

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

    def test_home_lists_recommended_before_new(self):
        make_event("おすすめ公演", start=self.now + timedelta(days=1), tier=Event.ListingTier.FEATURED)
        html = self.client.get(reverse("outings:home")).content.decode()
        self.assertLess(html.index("おすすめ"), html.index("新着"))




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

    def test_yapp_home_links_to_outings(self):
        self.assertContains(self.client.get(reverse("portal:home")), reverse("outings:home"))


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
        make_event("大人の会", start=self.now + timedelta(days=2))
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

    def test_home_shows_three_recommended_events_without_a_toggle(self):
        for i in range(5):
            make_event(f"注目{i}", start=self.now + timedelta(days=i + 1), tier=Event.ListingTier.FEATURED)
        html = self.client.get(reverse("outings:home")).content.decode()
        picks = html[html.index("home-picks"):html.index("home-fresh")]
        self.assertEqual(picks.count('class="discovery-card"'), 3)
        self.assertNotIn("data-discovery-toggle", html)

    def test_recommended_events_with_photo_come_first(self):
        make_event("写真なし", start=self.now + timedelta(days=1), tier=Event.ListingTier.FEATURED)
        make_event("写真あり", start=self.now + timedelta(days=3), tier=Event.ListingTier.FEATURED,
                   image_url="https://example.com/a.jpg")
        html = self.client.get(reverse("outings:home")).content.decode()
        self.assertLess(html.index("写真あり"), html.index("写真なし"))
        self.assertIn("card-tone--", html)


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
