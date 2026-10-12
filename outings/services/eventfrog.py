"""Read Eventfrog public API into normalized event candidates (no Django models)."""
import json
import os
import time
from datetime import timedelta
from zoneinfo import ZoneInfo

import requests
from django.utils import timezone
from django.utils.dateparse import parse_datetime

API_URL = 'https://api.eventfrog.net/public/v1/events'
LOCATION_URL = 'https://api.eventfrog.net/public/v1/locations'
TZ = ZoneInfo('Europe/Zurich')
REGIONS = {'ZH', 'AG', 'BE', 'BS', 'BL', 'LU', 'ZG'}
REGION_NAMES = {
    'ZÜRICH': 'ZH', 'ZURICH': 'ZH', 'AARGAU': 'AG', 'BERN': 'BE',
    'BASEL-STADT': 'BS', 'BASEL-LANDSCHAFT': 'BL', 'LUZERN': 'LU',
    'LUCERNE': 'LU', 'ZUG': 'ZG',
}

# The Eventfrog /locations API usually returns city/title/zip but no canton.
# Assign only unambiguous known municipality names. Unknown cities are held.
CITY_TO_REGION = {
    'ZÜRICH': 'ZH', 'ZURICH': 'ZH', 'ZUERICH': 'ZH',
    'WINTERTHUR': 'ZH', 'USTER': 'ZH', 'DIETIKON': 'ZH',
    'DÜBENDORF': 'ZH', 'DUEBENDORF': 'ZH', 'BÜLACH': 'ZH',
    'BUELACH': 'ZH', 'HORGEN': 'ZH', 'WÄDENSWIL': 'ZH',
    'WAEDENSWIL': 'ZH', 'KLOTEN': 'ZH', 'SCHLIEREN': 'ZH',
    'OPFIKON': 'ZH', 'WETZIKON': 'ZH', 'MEILEN': 'ZH',
    'BASSEL': 'BS', 'BASEL': 'BS', 'RIEHEN': 'BS', 'BETTINGEN': 'BS',
    'LIESTAL': 'BL', 'MUTTENZ': 'BL', 'PRATTELN': 'BL',
    'ALLSCHWIL': 'BL', 'BIRSFELDEN': 'BL', 'REINACH BL': 'BL',
    'AARAU': 'AG', 'BADEN': 'AG', 'WETTINGEN': 'AG',
    'LENZBURG': 'AG', 'ZOFINGEN': 'AG', 'SPREITENBACH': 'AG',
    'RHEINFELDEN': 'AG', 'BRUGG': 'AG', 'WOHLEN AG': 'AG',
    'BERN': 'BE', 'BERNE': 'BE', 'THUN': 'BE',
    'BIEL': 'BE', 'BIENNE': 'BE', 'BIEL/BIENNE': 'BE',
    'BURGDORF': 'BE', 'INTERLAKEN': 'BE', 'SPIEZ': 'BE',
    'LUZERN': 'LU', 'LUCERNE': 'LU', 'KRIENS': 'LU',
    'EMMEN': 'LU', 'SURSEE': 'LU', 'HORW': 'LU',
    'ZUG': 'ZG', 'BAAR': 'ZG', 'CHAM': 'ZG',
    'STEINHAUSEN': 'ZG', 'ROTKREUZ': 'ZG', 'HÜNENBERG': 'ZG',
}


def translated(value):
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for lang in ('de', 'en', 'fr', 'it', 'ja'):
            if isinstance(value.get(lang), str) and value[lang].strip():
                return value[lang].strip()
        return next((v.strip() for v in value.values() if isinstance(v, str) and v.strip()), '')
    return ''


def dt(value):
    parsed = parse_datetime(str(value or ''))
    return parsed if parsed and timezone.is_aware(parsed) else None


def is_true(v):
    return v is True or str(v).lower() == 'true'


def find_in(obj, *keys):
    for key in keys:
        value = obj
        for part in key.split('.'):
            value = value.get(part) if isinstance(value, dict) else None
        if value not in (None, '', [], {}):
            return value
    return None


def location_ids(event):
    val = event.get('locationIds') or []
    if isinstance(val, str):
        try:
            val = json.loads(val)
        except ValueError:
            val = []
    return [str(v) for v in val] if isinstance(val, list) else []


def collect(*, pages=40, per_page=1000, days=45, raw_events=None):
    now = timezone.now()
    horizon = now + timedelta(days=days)
    if raw_events is not None:
        records = raw_events
    else:
        token = os.environ.get('EVENTFROG_API_TOKEN', '').strip()
        if not token:
            raise ValueError('EVENTFROG_API_TOKEN がありません')
        records = []
        with requests.Session() as session:
            session.headers.update({'Authorization': f'Bearer {token}', 'Accept': 'application/json'})
            for page in range(1, pages + 1):
                response = session.get(API_URL, params={
                    'country': 'CH', 'from': now.astimezone(TZ).isoformat(),
                    'to': horizon.astimezone(TZ).isoformat(), 'page': page,
                    'perPage': per_page,
                }, timeout=40)
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict) or not isinstance(payload.get('events'), list):
                    raise ValueError(f'Eventfrog response shape unexpected on page {page}')
                part = payload['events']
                records.extend(part)
                print(f'[Eventfrog] Events page {page}/{pages}: {len(part)} rows; total={len(records)}', flush=True)
                if len(part) < per_page or not part:
                    break
                time.sleep(1.2)

    result = {}
    cancelled = set()
    for item in records:
        if not isinstance(item, dict):
            continue
        ext_id = str(item.get('id') or '').strip()
        start, end = dt(item.get('begin')), dt(item.get('end'))
        if not ext_id or not start or not end or end <= start or not now <= start <= horizon:
            continue
        if is_true(item.get('cancelled')):
            cancelled.add(ext_id)
            continue
        if item.get('published') is not True or item.get('visible') is not True:
            continue
        title = translated(item.get('title'))
        url = str(item.get('url') or '').strip()
        if not title or not url.startswith('https://eventfrog.ch/') and not url.startswith('https://www.eventfrog.ch/'):
            continue
        from bs4 import BeautifulSoup
        desc = translated(item.get('descriptionAsHTML')) or translated(item.get('shortDescription'))
        desc = BeautifulSoup(desc, 'html.parser').get_text(' ', strip=True)[:1800]
        result[ext_id] = {
            'id': ext_id, 'group_id': str(item.get('groupId') or ''),
            'title': title[:250], 'description': desc,
            'start': start.isoformat(), 'end': end.isoformat(),
            'url': url, 'location_ids': location_ids(item),
            'organizer': translated(item.get('organizerName')),
            'image_url': translated(item.get('emblemToShow')) if isinstance(item.get('emblemToShow'), str) else '',
        }
    for ext_id in cancelled:
        result.pop(ext_id, None)
    return list(result.values())


def enrich_locations(events, *, offline=False, cache_file=None):
    """Rate-limit-aware location lookup with incremental disk cache."""
    cache = {}
    if cache_file and cache_file.exists():
        data = json.loads(cache_file.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            raise ValueError('Location cache must be a JSON object')
        cache = data
    ids = sorted({i for e in events for i in e['location_ids']})
    missing = [i for i in ids if i not in cache]
    print(f'[Eventfrog] Locations required={len(ids)} cached={len(ids)-len(missing)} missing={len(missing)}', flush=True)
    if missing and not offline:
        token = os.environ.get('EVENTFROG_API_TOKEN', '').strip()
        if not token:
            raise ValueError('EVENTFROG_API_TOKEN がありません')
        if cache_file:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
        with requests.Session() as session:
            session.headers.update({'Authorization': f'Bearer {token}', 'Accept': 'application/json'})
            chunk_size = 40
            for idx in range(0, len(missing), chunk_size):
                chunk = missing[idx:idx + chunk_size]
                for attempt in range(4):
                    try:
                        response = session.get(LOCATION_URL, params=[('id', x) for x in chunk], timeout=40)
                        if response.status_code in (429, 500, 502, 503, 504):
                            if attempt == 3:
                                response.raise_for_status()
                            retry_after = response.headers.get('Retry-After', '').strip()
                            try:
                                wait = min(180.0, max(1.0, float(retry_after)))
                            except ValueError:
                                wait = min(120.0, 15.0 * (2 ** attempt))
                            print(f'[Eventfrog] HTTP {response.status_code}, waiting {wait:g}s before retry ({attempt+1}/3)', flush=True)
                            time.sleep(wait)
                            continue
                        response.raise_for_status()
                        payload = response.json()
                        part = payload if isinstance(payload, list) else (payload.get('locations') or payload.get('items') or payload.get('data') or [])
                        if isinstance(part, dict):
                            part = part.get('locations') or part.get('items') or []
                        if not isinstance(part, list):
                            raise ValueError('Location API response shape unexpected')
                        for item in part:
                            if isinstance(item, dict) and item.get('id') is not None:
                                cache[str(item['id'])] = item
                        # Persist after EACH successful API response, not only at end.
                        if cache_file:
                            tmp = cache_file.with_name(cache_file.name + '.tmp')
                            tmp.write_text(json.dumps(cache, ensure_ascii=False), encoding='utf-8')
                            tmp.replace(cache_file)
                        print(f'[Eventfrog] Locations progress {min(idx+len(chunk),len(missing))}/{len(missing)}; cache={len(cache)}', flush=True)
                        break
                    except (requests.Timeout, requests.ConnectionError) as exc:
                        if attempt == 3:
                            raise
                        wait = min(60, 5 * (2 ** attempt))
                        print(f'[Eventfrog] Network error, retry in {wait}s: {type(exc).__name__}', flush=True)
                        time.sleep(wait)
                time.sleep(3.0)  # stay conservative with Eventfrog rate limits
    output = []
    for event in events:
        info = [cache[i] for i in event['location_ids'] if i in cache and isinstance(cache[i], dict)]
        resolved = []
        for loc in info:
            raw = translated(find_in(loc, 'canton', 'cantonCode', 'state', 'region', 'address.canton', 'address.state')).upper().strip()
            city = translated(find_in(loc, 'city', 'cityName', 'town', 'municipality', 'address.city')).strip()
            region = raw if raw in REGIONS else REGION_NAMES.get(raw, '')
            if not region:
                region = CITY_TO_REGION.get(city.upper(), '')
            venue = translated(find_in(loc, 'name', 'title', 'locationName')).strip()
            if region and city and venue:
                resolved.append((region, city, venue))
        # Reject conflicting canton assignments and unresolved/unknown locations.
        if not resolved or len({item[0] for item in resolved}) != 1:
            continue
        region, city, venue = resolved[0]
        output.append({**event, 'region': region, 'city': city, 'venue': venue})
    return output


def group(events):
    """Provisional grouping by title + venue + organizer; preserve all individual IDs."""
    import unicodedata
    def key(s):
        return ' '.join(unicodedata.normalize('NFKC', s).casefold().split())
    grouped = {}
    for e in events:
        group_key = (key(e['title']), e['region'], key(e['venue']), key(e['organizer']))
        if group_key not in grouped:
            grouped[group_key] = {**e, 'occurrences': []}
        grouped[group_key]['occurrences'].append({'id': e['id'], 'start': e['start'], 'end': e['end']})
    for event in grouped.values():
        event['occurrences'].sort(key=lambda x: x['start'])
        event['start'] = event['occurrences'][0]['start']
    return sorted(grouped.values(), key=lambda x: x['start'])
