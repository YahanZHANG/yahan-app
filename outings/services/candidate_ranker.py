"""Deterministic, no-API Eventfrog pre-screening for daily AI curation.

Do not classify uncertain events as junk. The AI editorial stage remains final.
"""

import re
from collections import Counter, defaultdict, deque
from datetime import datetime

from django.utils import timezone

from outings.regions import EVENTFROG_REGIONS as REGION_ORDER

# High-confidence administrative-only or private package offers.
REJECT_TITLE_PATTERNS = (
    re.compile(r"\b(?:sitzplatzreservation|platzreservation|tischreservation|seat reservation)\b", re.I),
    re.compile(r"\b(?:firmenevents?|teamevents?|firmenanlass|betriebsausflug)\s*[:\-–]", re.I),
    re.compile(r"\b(?:geschlossene gesellschaft|private firmenfeier|exklusiv für firmen)\b", re.I),
)

# Weak hints affect ordering only, never automatic publication or rejection.
POSITIVE_CUES = (
    "festival", "fest", "markt", "messe", "museum", "ausstellung", "konzert",
    "concert", "theater", "theatre", "familie", "kinder", "kind", "baby",
    "workshop", "führung", "fuehrung", "open air", "wander", "natur",
    "food", "streetfood", "street food", "jazz", "musik", "kunst", "kino",
    "spectacle", "marché", "exposition", "spectacle", "atelier",
)
WEAK_CUES = (
    "infoabend", "informationsabend", "beratung", "vorlesung",
    "lecture", "networking", "business lunch", "kursnr", "antrittsvorlesung",
)


def _bucket(event, now):
    try:
        start = datetime.fromisoformat(str(event["start"]).replace("Z", "+00:00"))
        if timezone.is_naive(start):
            return None
        delta_days = (start - now).total_seconds() / 86400
    except (ValueError, TypeError, KeyError):
        return None
    if delta_days < 0:
        # Already open (an exhibition): still listable while it runs.
        try:
            end = datetime.fromisoformat(str(event.get("end")).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
        if timezone.is_naive(end) or end <= now:
            return None
        delta_days = 0
    return 0 if delta_days < 7 else 1 if delta_days < 14 else 2 if delta_days < 21 else 3


def _quality_score(event):
    title = str(event.get("title") or "")
    description = str(event.get("description") or "")
    haystack = f"{title} {description[:800]}".casefold()
    score = sum(2 for cue in POSITIVE_CUES if cue in haystack)
    score -= sum(2 for cue in WEAK_CUES if cue in title.casefold())
    # Prefer listings with descriptions and a concrete venue over empty shells.
    score += 2 if len(description.strip()) >= 120 else 0
    score += 1 if event.get("venue") else 0
    return score


def rank_daily_candidates(events, *, now=None):
    """Return (ordered candidates, reject reasons).

    Fair interleave over (four time windows x seven cantons); no random state.
    Filter only high-confidence administrative offers. All other candidates
    remain eligible for editorial AI evaluation.
    """
    now = now or timezone.now()
    queues = defaultdict(list)
    reasons = Counter()
    for event in events:
        title = str(event.get("title") or "").strip()
        if not title or any(pattern.search(title) for pattern in REJECT_TITLE_PATTERNS):
            reasons["administrative_or_private_offer"] += 1
            continue
        band = _bucket(event, now)
        if band is None:
            reasons["invalid_or_past_date"] += 1
            continue
        region = str(event.get("region") or "").upper()
        if region not in REGION_ORDER:
            reasons["unsupported_region"] += 1
            continue
        queues[(band, region)].append(event)

    for group in queues.values():
        group.sort(
            key=lambda e: (
                -_quality_score(e),
                str(e.get("start") or ""),
                str(e.get("id") or ""),
            )
        )

    # Alternate the temporal band every selection; each region gets a chance.
    order = [(band, region) for band in range(4) for region in REGION_ORDER]
    queues = {key: deque(value) for key, value in queues.items()}
    result = []
    while True:
        added = False
        for key in order:
            queue = queues.get(key)
            if queue:
                result.append(queue.popleft())
                added = True
        if not added:
            break
    return result, dict(reasons)
