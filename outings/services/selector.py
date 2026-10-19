"""Pick which screened Eventfrog candidates to publish, with deduplication and variety."""
import re
import unicodedata
from datetime import datetime, timedelta

from django.utils import timezone

MIN_SCORE = 60
FEATURED_SCORE = 80
STANDARD_SCORE = 68

# Share of each run per first-date band: this week, next week, weeks 3-4, later.
BAND_SHARES = (30, 25, 25, 20)


def _parse(value):
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return dt if dt.tzinfo else None
    except (TypeError, ValueError):
        return None


def _live_occurrences(event, now, horizon):
    """Occurrences not over yet and starting inside the horizon (ongoing runs included)."""
    result = []
    for o in event.get('occurrences', []):
        if not isinstance(o, dict):
            continue
        start, end = _parse(o.get('start')), _parse(o.get('end'))
        if not start or start > horizon:
            continue
        if (end or start) <= now:
            continue
        result.append(o)
    return result


def _long_running(event, occurrences):
    for o in occurrences:
        start, end = _parse(o.get('start')), _parse(o.get('end'))
        if start and end and end - start >= timedelta(days=14):
            return True
    days = sorted({_parse(o['start']).date() for o in occurrences if _parse(o.get('start'))})
    return len(days) > 1 and (days[-1] - days[0]).days >= 14


def _recurring(occurrences):
    days = sorted({dt.date() for o in occurrences if (dt := _parse(o.get('start')))})
    return any((b - a).days in (7, 14) for a, b in zip(days, days[1:]))


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
        return ('title-place', title, venue, city, region)
    if group not in ('', '0', 'None') and title:
        return ('group-title', group, title, region)
    return ('id', str(event.get('id')))


def _merge_duplicates(screened):
    """Union performances of the same programme; keep the best screening."""
    merged = {}
    for item in screened:
        identity = _identity(item)
        if identity not in merged:
            merged[identity] = {**item, 'occurrences': list(item.get('occurrences') or [])}
            continue
        current = merged[identity]
        known = {(str(o.get('id')), str(o.get('start'))) for o in current['occurrences']}
        for occurrence in item.get('occurrences') or []:
            key = (str(occurrence.get('id')), str(occurrence.get('start')))
            if key not in known:
                current['occurrences'].append(occurrence)
                known.add(key)
        if (item.get('screen') or {}).get('score', 0) > (current.get('screen') or {}).get('score', 0):
            current['screen'] = item['screen']
    return list(merged.values())


def eligible(screen):
    score = screen.get('score')
    if not isinstance(score, int) or isinstance(score, bool) or score < MIN_SCORE:
        return False
    participation = screen.get('participation')
    return participation == 'drop_in' or (participation == 'unknown' and score >= 70)


def listing_tier(score, *, long_running, recurring):
    if score >= FEATURED_SCORE and not long_running and not recurring:
        return 'featured'
    if score >= STANDARD_SCORE:
        return 'standard'
    return 'compact'


def select(screened, *, target=15, now=None, days=30):
    """Return up to `target` candidates in priority order (best first)."""
    now = now or timezone.now()
    horizon = now + timedelta(days=days)
    bands = [[], [], [], []]
    for item in _merge_duplicates(screened):
        screen = item.get('screen') or {}
        if not eligible(screen):
            continue
        occurrences = _live_occurrences(item, now, horizon)
        if not occurrences:
            continue
        occurrences.sort(key=lambda o: o.get('start', ''))
        first_start = _parse(occurrences[0]['start'])
        long_running = _long_running(item, occurrences)
        recurring = _recurring(occurrences)
        event = {
            **item,
            'occurrences': occurrences,
            'is_long_running': long_running,
            'is_recurring': recurring,
            'first_upcoming_at': first_start.isoformat(),
            'listing_tier': listing_tier(screen['score'], long_running=long_running, recurring=recurring),
        }
        delta = max(0.0, (first_start - now).total_seconds() / 86400)
        band = 0 if delta <= 7 else 1 if delta <= 14 else 2 if delta <= 28 else 3
        bands[band].append(event)

    selected = []
    region_counts, category_counts = {}, {}
    long_cap = max(1, round(target * .2))
    long_count = 0

    def rank(x):
        screen = x['screen']
        penalty = 4 * region_counts.get(x.get('region'), 0) + 3 * category_counts.get(screen.get('category'), 0)
        return (-(screen['score'] - penalty), x['first_upcoming_at'], str(x.get('id')))

    def take(pool):
        nonlocal long_count
        options = [x for x in pool if not x['is_long_running'] or long_count < long_cap]
        if not options:
            return False
        winner = min(options, key=rank)
        pool.remove(winner)
        selected.append(winner)
        region_counts[winner.get('region')] = region_counts.get(winner.get('region'), 0) + 1
        category = winner['screen'].get('category')
        category_counts[category] = category_counts.get(category, 0) + 1
        long_count += int(winner['is_long_running'])
        return True

    for pool, share in zip(bands, BAND_SHARES):
        budget = round(target * share / 100)
        while pool and budget > 0 and len(selected) < target and take(pool):
            budget -= 1
    remaining = [x for pool in bands for x in pool]
    while remaining and len(selected) < target and take(remaining):
        pass
    return selected
