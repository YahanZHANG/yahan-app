"""What an event card shows: next date, badges, emoji. Shared by every listing."""

from django.utils import timezone

from .models import Event
from .services import schedule


EMOJI_KEYWORDS = [
    (["weihnacht", "christmas", "クリスマス", "advent"], "🎄"),
    (["halloween", "ハロウィン"], "🎃"),
    (["fasnacht", "fasnet", "carnival", "カーニバル"], "🎭"),
    (["baby", "ベビー", "赤ちゃん"], "👶"),
    (["kinder", "kids", "子ども", "こども", "親子"], "🧸"),
    (["markt", "market", "マーケット", "flohmarkt"], "🛍️"),
    (["festival", "fest", "祭り", "フェス"], "🎪"),
    (["museum", "美術館", "博物館"], "🏛️"),
    (["ausstellung", "exhibition", "展"], "🖼️"),
    (["jazz"], "🎷"),
    (["konzert", "concert", "コンサート", "musik", "music", "音楽"], "🎵"),
    (["comedy", "コメディ"], "🎤"),
    (["theater", "theatre", "劇", "舞台"], "🎭"),
    (["kino", "film", "cinema", "映画"], "🎬"),
    (["wein", "wine", "ワイン"], "🍷"),
    (["essen", "food", "グルメ", "料理"], "🍽️"),
    (["führung", "fuehrung", "tour", "ツアー", "街歩き"], "🚶"),
    (["wander", "hike", "ハイキング"], "🥾"),
    (["natur", "nature", "自然"], "🌿"),
    (["sport", "スポーツ"], "⚽"),
    (["workshop", "体験", "ワークショップ"], "✂️"),
    (["schloss", "castle", "城"], "🏰"),
]

CATEGORY_EMOJI = {
    "festival": "🎪", "market": "🛍️", "seasonal": "🍂", "art": "🎨", "museum": "🏛️",
    "music": "🎵", "theater": "🎭", "comedy": "🎤", "film": "🎬", "food": "🍽️",
    "workshop": "✂️", "family": "🧸", "tour": "🚶", "nature": "🌿", "sports": "⚽",
}


# Colour family for cards without a photo (see .card-tone--* in outings-v2.css).
CATEGORY_TONE = {
    "music": "stage", "theater": "stage", "comedy": "stage", "film": "stage",
    "art": "art", "museum": "art",
    "festival": "fest", "market": "fest", "seasonal": "fest", "food": "fest",
    "family": "family",
    "tour": "nature", "nature": "nature", "sports": "nature", "outdoor": "nature",
    "workshop": "craft",
}


def event_tone(event):
    if event.category_id and event.category:
        return CATEGORY_TONE.get(event.category.slug, "default")
    return "default"


def event_emoji(event):
    text = f"{event.title or ''} {event.title_original or ''}".lower()
    for words, emoji in EMOJI_KEYWORDS:
        if any(word in text for word in words):
            return emoji
    if event.category_id and event.category:
        return CATEGORY_EMOJI.get(event.category.slug, "🎈")
    return "🎈"


def badges(event):
    """Short labels shown under the title, in order of usefulness."""
    result = []
    tags = {tag.slug for tag in event.tags.all()}
    if event.is_free:
        result.append(("無料", "free"))
    lang = event.language_barrier
    if lang == Event.LanguageBarrier.NONE:
        result.append(("言葉がわからなくてもOK", "ok"))
    elif lang in (Event.LanguageBarrier.ENGLISH, Event.LanguageBarrier.JAPANESE):
        result.append((event.get_language_barrier_display() + "OK", "ok"))
    elif lang in (Event.LanguageBarrier.GERMAN_REQUIRED, Event.LanguageBarrier.FRENCH_REQUIRED, Event.LanguageBarrier.ITALIAN_REQUIRED):
        result.append((event.get_language_barrier_display().split("（")[0] + "が必要", "warn"))
    if tags & {"family", "children", "baby"}:
        result.append(("子連れOK" if "baby" in tags else "家族向け", "family"))
    if "japan" in tags:
        result.append(("日本関連", "japan"))
    if event.source_id is None:
        result.append(("みんなの投稿", "community"))
    return result


def decorate(event, now=None, hearted_ids=()):
    """Attach card fields to an Event that has `upcoming_dates` prefetched."""
    now = now or timezone.now()
    dates = getattr(event, "upcoming_dates", None)
    if dates is None:
        dates = schedule.upcoming(event.occurrences.all(), now)
    event.upcoming_dates = dates
    event.next_occurrence = dates[0] if dates else None
    event.date_label = schedule.occurrence_label(dates[0], now) if dates else ""
    event.more_dates = max(0, len(dates) - 1)
    event.is_long = schedule.is_long_running(dates)
    event.display_emoji = event_emoji(event)
    event.badges = badges(event)
    event.is_hearted = event.pk in hearted_ids
    return event
