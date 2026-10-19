"""Publish curated Eventfrog candidates as Event rows.

Identity resolution keeps existing Event rows (and their hearts, comments and
occurrence IDs) when a programme comes back under another representative ID.
One invalid row is skipped and reported; it never blocks the rest of the run.
"""
import re
from datetime import datetime
from urllib.parse import urlparse

from django.db import transaction
from django.utils import timezone

from outings.models import (
    Event, EventCategory, EventLocation, EventOccurrence, EventSource, EventTag,
    EventfrogOccurrenceLink,
)

CATEGORY_NAMES = {
    'festival': 'お祭り・フェス', 'market': 'マーケット', 'seasonal': '季節の行事',
    'art': 'アート', 'museum': '博物館・展示', 'music': '音楽', 'theater': '演劇・ダンス',
    'comedy': 'コメディ・ナイト', 'film': '映画', 'food': 'グルメ',
    'workshop': '体験・ワークショップ', 'family': '親子・家族', 'tour': 'ツアー・街歩き',
    'nature': '自然', 'sports': 'スポーツ', 'other': 'その他',
}
TAG_NAMES = {'family': '家族向け', 'children': '子ども向け', 'baby': '赤ちゃん', 'japan': '日本関連'}
TIERS = {'featured', 'standard', 'compact'}
# Respect manual rejection or cancellation and pending review.
PROTECTED_STATUSES = (Event.Status.PENDING, Event.Status.REJECTED, Event.Status.CANCELLED)


class InvalidRow(ValueError):
    pass


def as_datetime(raw):
    try:
        obj = datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return None
    return obj if timezone.is_aware(obj) else None


def editorial(item):
    """One view over the new (screen + article) and the legacy (ai) formats."""
    if isinstance(item.get('article'), dict):
        article, screen = item['article'], item.get('screen') or {}
        return {**article, 'score': screen.get('score')}
    ai = item.get('ai')
    if isinstance(ai, dict):
        return {
            'title_ja': ai.get('title_ja'), 'summary_ja': ai.get('summary_ja'),
            'highlight_ja': '', 'category': ai.get('category'), 'tags': ai.get('tags') or [],
            'language_barrier': ai.get('language_barrier'), 'is_free': None, 'price_text': '',
            'age_note': '', 'booking': 'unknown', 'setting': 'unknown', 'score': ai.get('score'),
        }
    raise InvalidRow('missing article')


def validate(item):
    if not isinstance(item, dict):
        raise InvalidRow('not an object')
    ed = editorial(item)
    eid = str(item.get('id') or '').strip()
    if not eid:
        raise InvalidRow('missing id')
    if str(item.get('listing_tier') or '') not in TIERS:
        raise InvalidRow(f'{eid}: invalid listing_tier')
    if not ed.get('title_ja'):
        raise InvalidRow(f'{eid}: missing title_ja')
    if not (item.get('region') and item.get('city') and item.get('venue')):
        raise InvalidRow(f'{eid}: missing place')
    url = str(item.get('url') or '')
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in ('eventfrog.ch', 'www.eventfrog.ch'):
        raise InvalidRow(f'{eid}: not an Eventfrog URL')
    # A wrong article URL must never be saved.
    url_id = re.search(r'-(\d+)\.html$', parsed.path)
    allowed = {eid, *(str(o.get('id')) for o in item.get('occurrences', []) if isinstance(o, dict) and o.get('id'))}
    if not url_id or url_id.group(1) not in allowed:
        raise InvalidRow(f'{eid}: Eventfrog URL does not match the event ID')
    dates = []
    for o in item.get('occurrences', []):
        if not isinstance(o, dict):
            continue
        start, end = as_datetime(o.get('start')), as_datetime(o.get('end'))
        if start and (not end or end >= start):
            dates.append((o, start, end))
    if not dates:
        raise InvalidRow(f'{eid}: no valid dates')
    return ed, dates


def import_items(items, *, log=print, warn=print):
    """Create or update published events. Returns counts."""
    stats = {'created': 0, 'updated': 0, 'skipped': 0, 'invalid': 0}
    cleaned, seen = [], set()
    for index, item in enumerate(items, 1):
        try:
            ed, dates = validate(item)
        except InvalidRow as exc:
            warn(f'SKIP row {index}: {exc}')
            stats['invalid'] += 1
            continue
        if str(item['id']) in seen:
            warn(f'SKIP row {index}: duplicate {item["id"]}')
            stats['invalid'] += 1
            continue
        seen.add(str(item['id']))
        cleaned.append((item, ed, dates))

    source, _ = EventSource.objects.get_or_create(name='Eventfrog', defaults={'website_url': 'https://eventfrog.ch/'})
    claimed = set()
    for item, ed, dates in cleaned:
        try:
            with transaction.atomic():
                outcome = _import_one(item, ed, dates, source, claimed, warn)
        except InvalidRow as exc:
            warn(f'SKIP {item["id"]}: {exc}')
            outcome = 'skipped'
        stats[outcome] += 1
    log(f'Imported Eventfrog events: {stats}')
    return stats


def _import_one(item, ed, dates, source, claimed, warn):
    eid = str(item['id'])
    occurrence_ids = {str(o.get('id')).strip() for o, _, _ in dates if o.get('id') not in (None, '')}
    owner_ids = set(EventfrogOccurrenceLink.objects.filter(eventfrog_id__in=occurrence_ids).values_list('event_id', flat=True))
    by_external_id = Event.objects.filter(source=source, external_id=eid).first()
    if len(owner_ids) > 1:
        raise InvalidRow(f'occurrences belong to several events {sorted(owner_ids)}; review manually')
    if owner_ids:
        owner_id = next(iter(owner_ids))
        existing = Event.objects.filter(pk=owner_id, source=source).first()
        if existing is None or (by_external_id and by_external_id.pk != owner_id):
            raise InvalidRow('ambiguous owner; review manually')
    else:
        existing = by_external_id
    if existing and existing.pk in claimed:
        raise InvalidRow(f'Event {existing.pk} already used by another row')
    if existing and existing.status in PROTECTED_STATUSES:
        return 'skipped'

    slug = ed.get('category') if ed.get('category') in CATEGORY_NAMES else 'other'
    category, _ = EventCategory.objects.get_or_create(slug=slug, defaults={'name': CATEGORY_NAMES[slug]})
    location, _ = EventLocation.objects.get_or_create(
        name=str(item['venue']).strip()[:200], city=str(item['city']).strip()[:120],
        canton=str(item['region']).strip()[:10], address='', defaults={},
    )
    lang = str(ed.get('language_barrier') or 'unknown')
    if lang not in {x for x, _ in Event.LanguageBarrier.choices}:
        lang = 'unknown'
    score = ed.get('score')
    setting = ed.get('setting')
    if len(dates) > 1 and not item.get('is_long_running'):
        event_type = Event.EventType.RECURRING
    elif item.get('is_long_running'):
        event_type = Event.EventType.LONG_RUNNING
    else:
        event_type = Event.EventType.ONE_TIME
    values = {
        'title': str(ed['title_ja']).strip()[:250],
        'title_original': str(item.get('title') or '')[:250],
        'summary_ja': str(ed.get('summary_ja') or ''),
        'highlight_ja': str(ed.get('highlight_ja') or '')[:120],
        'description_original': str(item.get('description') or ''),
        'listing_tier': str(item['listing_tier']),
        'event_type': event_type,
        'status': Event.Status.PUBLISHED,
        'category': category,
        'location': location,
        'language_barrier': lang,
        'is_free': ed.get('is_free') is True,
        'price_text': str(ed.get('price_text') or '')[:150],
        'is_indoor': setting in ('indoor', 'both'),
        'is_outdoor': setting in ('outdoor', 'both'),
        'original_url': str(item['url']),
        'ai_score': score if isinstance(score, int) and 0 <= score <= 100 else None,
        'ai_details': {
            'age_note': ed.get('age_note') or '',
            'booking': ed.get('booking') or 'unknown',
            'price_known': ed.get('is_free') is not None or bool(ed.get('price_text')),
            'screen': (item.get('screen') or {}).get('scores'),
            'version': ed.get('version', 'legacy'),
        },
        'ai_processed_at': timezone.now(),
    }
    image = str(item.get('image_url') or '').strip()
    if existing:
        event = existing
        for key, value in values.items():
            setattr(event, key, value)
        # Keep an image already copied to Cloudinary.
        if image and 'res.cloudinary.com/' not in (event.image_url or ''):
            event.image_url = image if urlparse(image).scheme == 'https' else event.image_url
        event.save()
        outcome = 'updated'
    else:
        event = Event.objects.create(
            source=source, external_id=eid,
            image_url=image if urlparse(image).scheme == 'https' else '',
            **values,
        )
        outcome = 'created'
    claimed.add(event.pk)
    tags = [
        EventTag.objects.get_or_create(slug=t, defaults={'name': TAG_NAMES[t]})[0]
        for t in sorted({t for t in ed.get('tags') or [] if t in TAG_NAMES})
    ]
    event.tags.set(tags)
    # Keep existing occurrence PKs, comments and hearts intact; upsert by start time.
    for occurrence, start, end in dates:
        obj, _ = EventOccurrence.objects.update_or_create(
            event=event, start_at=start, defaults={'end_at': end, 'is_cancelled': False},
        )
        occurrence_id = str(occurrence.get('id') or '').strip()
        if not occurrence_id:
            continue
        link = EventfrogOccurrenceLink.objects.filter(eventfrog_id=occurrence_id).first()
        if link is None:
            EventfrogOccurrenceLink.objects.create(
                eventfrog_id=occurrence_id, event=event, occurrence=obj, last_source_start_at=start,
            )
        elif link.event_id == event.pk:
            link.occurrence = obj
            link.last_source_start_at = start
            link.save(update_fields=['occurrence', 'last_source_start_at', 'last_seen_at'])
        else:
            raise InvalidRow(f'occurrence {occurrence_id} belongs to another event')
    return outcome
