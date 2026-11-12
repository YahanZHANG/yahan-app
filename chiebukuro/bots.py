"""
つぶやきBot。

- スイスを知ろうBot: 毎朝8時。文章は data/bot_swiss.json (Taro さんが書いたもの)
- スイスで和食Bot: 月・水・金の12時。公開中のレシピから1つ
- おでかけBot: 火・木・土の12時。木曜は今週末のイベント、火・土はスイスの行き先
- SwissNews Bot: 毎日17時。その日に話題になったニュース3〜5本

予約 (BotPost) は前もって作っておき、時間になったら、掲示板が開かれたときに
つぶやき (Post) にする (質問の小出しと同じ。新しい定期実行はいらない)。
"""

import json
import logging
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)

ZURICH = ZoneInfo("Europe/Zurich")
SWISS_DATA = Path(__file__).resolve().parent / "data" / "bot_swiss.json"

# 試運転: 2026-11-12 から30日間
TRIAL_START = date(2026, 11, 12)
TRIAL_DAYS = 30

SWISS_AT = time(8, 0)
LUNCH_AT = time(12, 0)
NEWS_AT = time(17, 0)
# お昼の Bot: 月・水・金 = 和食、火・木・土 = おでかけ、日曜はお休み
LUNCH_BOTS = {0: "washoku", 1: "outings", 2: "washoku", 3: "outings", 4: "washoku", 5: "outings"}
# 自動で作る Bot は、時間をこれ以上すぎたら出さない (古いニュースなどを出さないため)
LATE_LIMIT = timedelta(hours=6)
WEEKDAYS = "月火水木金土日"


def swiss_rows():
    with open(SWISS_DATA, encoding="utf-8") as handle:
        return json.load(handle)


def at(day, clock):
    return datetime.combine(day, clock, tzinfo=ZURICH)


def schedule(BotPost, start=TRIAL_START, days=TRIAL_DAYS):
    """
    予約を作る (すでにある予約はそのまま)。マイグレーションからも呼ぶので、モデルは引数で受け取る。
    スイスを知ろうBot: Day 0 (はじめのあいさつ) は初日の 7:59、Day n は (初日 + n-1) 日の 8:00。
    """

    created = 0

    def add(bot, when, **fields):
        nonlocal created
        _, made = BotPost.objects.get_or_create(bot=bot, publish_at=when, defaults=fields)
        created += made

    for row in swiss_rows():
        number = row["day"]
        if number > days:
            continue
        when = at(start, time(7, 59)) if number == 0 else at(start + timedelta(days=number - 1), SWISS_AT)
        add(
            "swiss", when, day=number, theme=row.get("theme", ""), title=row.get("title", ""),
            body=row["body"], source_url=row.get("source", ""),
        )
    for offset in range(days):
        day = start + timedelta(days=offset)
        lunch = LUNCH_BOTS.get(day.weekday())
        if lunch:
            add(lunch, at(day, LUNCH_AT), day=offset + 1)
        add("news", at(day, NEWS_AT), day=offset + 1)
    return created


# =========================================================
# 投稿
# =========================================================

def bot_user(bot):
    """Bot ごとのアカウント (ログインはできない)"""

    from django.contrib.auth import get_user_model

    from .models import BOT_NAMES

    User = get_user_model()
    user, made = User.objects.get_or_create(username=f"yapp_bot_{bot}", defaults={"is_active": False})
    if made:
        user.set_unusable_password()
        user.first_name = BOT_NAMES.get(bot, "Bot")[:150]
        user.save(update_fields=["password", "first_name"])
    return user


def release_due(now=None, limit=10):
    """時間になった予約をつぶやきにする。出した数を返す"""

    from .models import BotPost

    now = now or timezone.now()
    released = 0
    due = list(BotPost.objects.filter(state=BotPost.State.WAITING, publish_at__lte=now).order_by("publish_at", "pk")[:limit])
    for slot in due:
        # 同時に開かれても1回だけ出す
        if not BotPost.objects.filter(pk=slot.pk, state=BotPost.State.WAITING).update(state=BotPost.State.SKIPPED):
            continue
        try:
            post, note = publish(slot, now)
        except Exception:
            logger.exception("bot post %s failed", slot.pk)
            post, note = None, "エラーで出せませんでした"
        slot.post = post
        slot.state = BotPost.State.POSTED if post else BotPost.State.SKIPPED
        slot.note = note[:200]
        slot.save(update_fields=["post", "state", "note", "ref"])
        released += bool(post)
    return released


def publish(slot, now):
    """1件の予約をつぶやきにする。(つぶやき or None, メモ)"""

    from .models import BOT_NAMES, Post

    if not slot.is_active:
        return None, "オフにしてあったので出していません"
    if slot.body:
        content = {"tag": slot.theme, "title": slot.title, "body": slot.body, "links": []}
        if slot.source_url:
            content["body"] += f"\n\n出典：{slot.source_url}"
    else:
        if now - slot.publish_at > LATE_LIMIT:
            return None, "時間をすぎていたので出していません"
        builder = BUILDERS.get(slot.bot)
        content = builder(slot, now) if builder else None
        if not content:
            return None, "出せるデータがありませんでした"
        slot.ref = content.get("ref", "")[:40]
    post = Post.objects.create(
        bot=slot.bot,
        bot_tag=content.get("tag", "")[:40],
        title=content.get("title", "")[:120],
        body=content["body"],
        links=content.get("links", []),
        photo_url=content.get("photo", "") or "",
        author=bot_user(slot.bot),
        nickname=BOT_NAMES.get(slot.bot, "Bot"),
        created_at=slot.publish_at,
    )
    return post, ""


def outings_photo_source(post):
    """Botのつぶやきの写真の元 (おでかけの行き先・イベント)。(target, obj) か None"""

    from .models import BotPost

    slot = BotPost.objects.filter(post=post, bot="outings").first()
    if not slot or ":" not in slot.ref:
        return None
    kind, _, pk = slot.ref.partition(":")
    target = {"spot": "trip", "event": "event"}.get(kind)
    if not target or not pk.isdigit():
        return None
    from outings.models import Event, TouristSpot

    model = TouristSpot if target == "trip" else Event
    obj = model.objects.filter(pk=int(pk)).first()
    return (target, obj) if obj else None


def change_photo(post, url, credit="", kind="upload", source_url="", license_url=""):
    """
    運営がつぶやきの写真を差し替える (url) か消す ("")。
    おでかけBotのときは、おでかけアプリの行き先・イベントの写真も同じにする。
    本文の最後のクレジットの行 (📷 …) は、新しい写真のものに入れかえる。
    """

    lines = post.body.split("\n")
    while len(lines) > 1 and (lines[-1].startswith("📷 ") or not lines[-1].strip()):
        lines.pop()
    post.body = "\n".join(lines) + (photo_credit(credit) if url else "")
    post.photo_url = url
    post.save(update_fields=["photo_url", "body"])
    source = outings_photo_source(post) if post.bot == "outings" else None
    if not source:
        return False
    from outings import photo_admin

    target, obj = source
    old = photo_admin.current_url(target, obj)
    if url:
        photo_admin.set_photo(target, obj, url, credit, kind, source_url, license_url)
    else:
        photo_admin.remove_photo(target, obj)
    if old and old != url:
        photo_admin._delete_old(old)
    return True


def used_refs(bot, prefix, days=120):
    from .models import BotPost

    since = timezone.now() - timedelta(days=days)
    refs = BotPost.objects.filter(bot=bot, state=BotPost.State.POSTED, publish_at__gte=since, ref__startswith=prefix).values_list("ref", flat=True)
    return {int(ref.split(":", 1)[1]) for ref in refs if ref.split(":", 1)[1].isdigit()}


def short(text, limit=150):
    """長い紹介文を、文の切れ目で短くする"""

    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = cut.rfind("。")
    return cut[: end + 1] if end > limit // 3 else cut.rstrip() + "…"


def photo_credit(credit, about=""):
    """写真の出典 (Wikimedia などはクレジットが必要)"""

    credit = " ".join((credit or "").split())
    if not credit:
        return ""
    return f"\n\n📷 {about + '：' if about else ''}{credit}"[:300]


def build_washoku(slot, now):
    from washoku.models import Recipe

    recipes = Recipe.objects.filter(status="published")
    recipe = recipes.exclude(pk__in=used_refs("washoku", "recipe:")).order_by("?").first() or recipes.order_by("?").first()
    if not recipe:
        return None
    lines = [short(recipe.description)] if recipe.description else []
    if recipe.cooking_time_minutes:
        lines.append(f"⏱ 調理時間 約{recipe.cooking_time_minutes}分")
    lines.append("")
    lines.append("スイスで手に入る材料で作れるレシピだよ。作ったことがある人は、感想やコツを返信で教えてね😊")
    return {
        "tag": "🍱 今日の一品",
        "title": recipe.name,
        "body": "\n".join(lines),
        "links": [{"label": "レシピを見る（スイスで和食）", "url": reverse("washoku:recipe_detail", args=[recipe.pk])}],
        "photo": recipe.photo_1,
        "ref": f"recipe:{recipe.pk}",
    }


def build_weekend(slot, now):
    from .services import weekend_outings

    events = weekend_outings(limit=4)
    if not events:
        return None
    links = []
    for event in events:
        when = timezone.localtime(event.when)
        city = getattr(getattr(event, "location", None), "city", "") or ""
        label = f"{when.month}/{when.day}（{WEEKDAYS[when.weekday()]}）{event.title}" + (f"（{city}）" if city else "")
        links.append({"label": label, "url": reverse("outings:event_detail", args=[event.pk])})
    links.append({"label": "ほかのイベントを見る（おでかけ）", "url": reverse("outings:home")})
    pictured = next((event for event in events if event.image_url and not getattr(event, "image_removed", False)), None)
    return {
        "tag": "🏔️ 今週末のおでかけ",
        "title": "今週末、どこに行く？",
        "body": "今週末にスイスで開かれるイベントから、いくつか選んでみたよ。ほかにもおすすめがあれば、返信で教えてね！"
        + photo_credit(pictured.image_credit if pictured else "", pictured.title if pictured else ""),
        "links": links,
        "photo": pictured.image_url if pictured else "",
        "ref": f"event:{pictured.pk}" if pictured else "weekend",
    }


def build_spot(slot, now):
    from outings.models import TouristSpot

    spots = TouristSpot.objects.filter(status=TouristSpot.Status.PUBLISHED).exclude(intro_ja="")
    fresh = spots.exclude(pk__in=used_refs("outings", "spot:"))
    # 写真のある行き先を先に選ぶ
    with_photo = [
        pk for pk, details in fresh.values_list("pk", "details")
        if isinstance(details, dict) and not details.get("photo_removed") and (details.get("approved_image") or {}).get("url")
    ]
    spot = (
        (fresh.filter(pk__in=with_photo).order_by("?").first() if with_photo else None)
        or fresh.order_by("?").first() or spots.order_by("?").first()
    )
    if not spot:
        return None
    details = spot.details or {}
    image = {} if details.get("photo_removed") else (details.get("approved_image") or {})
    return {
        "tag": "🏔️ スイスの行き先",
        "title": spot.title_ja or spot.title_original,
        "body": short(spot.intro_ja) + "\n\n行ったことがある人は、おすすめの過ごし方を返信で教えてね！" + photo_credit(image.get("credit", "") if image.get("url") else ""),
        "photo": image.get("url", ""),
        "links": [{"label": "くわしく見る（おでかけ）", "url": reverse("outings:tourist_spot_detail", args=[spot.pk])}],
        "ref": f"spot:{spot.pk}",
    }


def build_outings(slot, now):
    """木曜は今週末のイベント (なければ行き先)、ほかの日はスイスの行き先"""

    if timezone.localtime(slot.publish_at).weekday() == 3:
        content = build_weekend(slot, now)
        if content:
            return content
    return build_spot(slot, now)


def build_news(slot, now):
    from news.models import Article
    from news.services.deduplicator import with_source_count

    articles = Article.objects.filter(
        Q(original_language="ja") | Q(ai_processed_at__isnull=False),
        duplicate_of__isnull=True,
        published_at__gte=now - timedelta(hours=24),
    )
    rows = list(with_source_count(articles).order_by("-source_count", "-life_alert", "-published_at")[:5])
    rows = [row for row in rows if (row.title_ja or row.title_original).strip()]
    if len(rows) < 3:
        return None
    links = [{"label": (row.title_ja or row.title_original).strip()[:90], "url": reverse("news:article_detail", args=[row.pk])} for row in rows]
    links.append({"label": "ほかのニュースを見る（SwissNews）", "url": reverse("news:home")})
    return {
        "tag": "📰 今日のニュース",
        "title": "今日のスイス、気になるニュース",
        "body": f"今日スイスで話題になったニュースを{len(rows)}本まとめたよ。気になったものがあったら、ひとこと返信してね。",
        "links": links,
        "ref": "news:" + ",".join(str(row.pk) for row in rows)[:30],
    }


BUILDERS = {"washoku": build_washoku, "outings": build_outings, "news": build_news}
