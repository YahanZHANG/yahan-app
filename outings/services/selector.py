"""Curate events with conservative listing tiers, deduplication and long-run limits."""
import re
import unicodedata
from datetime import datetime, timedelta
from django.utils import timezone

FEATURED_IDS = {'7511400660694248416', '7483163462182417413'}


def _parse(value):
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return dt if dt.tzinfo else None
    except (TypeError, ValueError):
        return None


def _future_occurrences(event, now, horizon):
    return [o for o in event.get('occurrences', []) if isinstance(o, dict)
            and (dt := _parse(o.get('start'))) and now <= dt <= horizon]


def _long_running(event, occurrences):
    start, end = _parse(event.get('start')), _parse(event.get('end'))
    if start and end and end - start >= timedelta(days=14):
        return True
    days = sorted({_parse(o['start']).date() for o in occurrences if _parse(o.get('start'))})
    streak = 1
    for a, b in zip(days, days[1:]):
        streak = streak + 1 if (b - a).days == 1 else 1
        if streak >= 14:
            return True
    return False

def _recurring_event(occurrences):
    """
    Detect weekly or biweekly recurring events.

    Two different occurrence dates exactly 7 or 14 days
    apart are treated as a recurring schedule.
    """

    dates = sorted({
        dt.date()
        for occurrence in occurrences
        if (dt := _parse(occurrence.get("start")))
    })

    return any(
        (next_date - current_date).days in (7, 14)
        for current_date, next_date in zip(
            dates,
            dates[1:],
        )
    )

def _normal(text):
    text = unicodedata.normalize('NFKC', str(text or '')).casefold()
    return re.sub(r'[^\w]+', '', text, flags=re.UNICODE)


def _identity(event):
    """A shared group alone is NOT enough: it may contain different events."""
    title = _normal(event.get('title'))
    venue = _normal(event.get('venue'))
    city = _normal(event.get('city'))
    region = _normal(event.get('region'))
    group = str(event.get('group_id') or '').strip()
    if title and venue and (city or region):
        # Repeated performances of the same programme at the same place.
        return ('title-place', title, venue, city, region)
    if group not in ('', '0', 'None') and title:
        return ('group-title', group, title, region)
    return ('id', str(event.get('id')))


def _merge_duplicates(evaluated):
    """Deduplicate before quotas; union performances, retain strongest assessment."""
    merged = {}
    for item in evaluated:
        identity = _identity(item)
        if identity not in merged:
            merged[identity] = {**item, 'occurrences': list(item.get('occurrences') or [])}
            continue
        current = merged[identity]
        known = {(str(o.get('id')), str(o.get('start'))) for o in current['occurrences']}
        for occurrence in item.get('occurrences') or []:
            identity_o = (str(occurrence.get('id')), str(occurrence.get('start')))
            if identity_o not in known:
                current['occurrences'].append(occurrence)
                known.add(identity_o)
        ai_old, ai_new = current.get('ai') or {}, item.get('ai') or {}
        old_rank = (ai_old.get('decision') == 'yes', ai_old.get('score', 0))
        new_rank = (ai_new.get('decision') == 'yes', ai_new.get('score', 0))
        if new_rank > old_rank:
            current['ai'] = ai_new
        if str(item.get('id')) in FEATURED_IDS:
            current['editorial_featured'] = True
    return list(merged.values())


def _tier(item, ai, score):
    if item.get('editorial_featured') or str(item.get('id')) in FEATURED_IDS or score >= 85:
        return 'featured'
    # A worthwhile but less universally accessible event belongs in a title-led list.
    # Do not exclude it just because it requires a local language.
    if score < 75 or (score < 80 and ai.get('language_barrier') in ('german_required', 'french_required')):
        return 'compact'
    return 'standard'


def select(evaluated, *, target=100, now=None, days=45):
    now = now or timezone.now()
    horizon = now + timedelta(days=days)
    budgets = [round(target * x / 100) for x in (25, 25, 30, 20)]
    buckets = [[], [], [], []]
    for item in _merge_duplicates(evaluated):
        ai = item.get('ai') or {}
        score = ai.get('score', 0)
        if ai.get('decision') != 'yes' or type(score) is not int or score < 60:
            continue
        if ai.get('participation_type') in ('series_course', 'restricted'):
            continue
        occurrences = _future_occurrences(item, now, horizon)
        if not occurrences:
            continue
        event = {**item, 'ai': dict(ai)}
        first_start = min(_parse(o['start']) for o in occurrences)
        delta = (first_start - now).total_seconds() / 86400
        band = 0 if delta <= 7 else 1 if delta <= 14 else 2 if delta <= 30 else 3
        event["is_long_running"] = _long_running(
            event,
            occurrences,
        )

        event["is_recurring"] = _recurring_event(
            event.get("occurrences") or []
        )
        tags = [tag for tag in ai.get('tags', []) if tag not in ('weekend', 'free', 'indoor', 'outdoor', 'low-language-barrier')]
        if any(_parse(o['start']).weekday() >= 5 for o in occurrences):
            tags.append('weekend')
        event['ai']['tags'] = list(dict.fromkeys(tags))
        event["listing_tier"] = _tier(event, ai, score)

        # Long-running and regularly recurring events
        # must not appear in Featured.
        if (
            event["listing_tier"] == "featured"
            and (
                event["is_long_running"]
                or event["is_recurring"]
            )
        ):
            event["listing_tier"] = "standard"

        event["show_summary_on_listing"] = (
            event["listing_tier"] in ("featured", "standard")
        )
        event['first_upcoming_at'] = first_start.isoformat()
        event['occurrences'] = sorted(event['occurrences'], key=lambda o: o.get('start', ''))
        buckets[band].append(event)

    selected = []
    counts_region, counts_category = {}, {}
    long_count = 0
    long_cap = max(1, round(target * .15))

    def rank(x):
        ai = x['ai']
        return (-(ai['score'] - 3 * counts_region.get(x.get('region'), 0)
                  - 2 * counts_category.get(ai.get('category'), 0)), x['first_upcoming_at'])

    def add(x):
        nonlocal long_count
        selected.append(x)
        counts_region[x.get('region')] = counts_region.get(x.get('region'), 0) + 1
        category = x['ai'].get('category')
        counts_category[category] = counts_category.get(category, 0) + 1
        long_count += int(x['is_long_running'])

    for band, budget in enumerate(budgets):
        while buckets[band] and len(selected) < target and budget > 0:
            options = [x for x in buckets[band] if not x['is_long_running'] or long_count < long_cap]
            if not options:
                break
            winner = min(options, key=rank)
            buckets[band].remove(winner)
            add(winner)
            budget -= 1
    remaining = [x for bucket in buckets for x in bucket]
    while remaining and len(selected) < target:
        options = [x for x in remaining if not x['is_long_running'] or long_count < long_cap]
        if not options:
            break
        winner = min(options, key=rank)
        remaining.remove(winner)
        add(winner)
    return sorted(selected, key=lambda x: x['first_upcoming_at'])
