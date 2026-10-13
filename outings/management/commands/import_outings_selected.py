"""Import curated Eventfrog events as published; dry-run by default."""
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from outings.models import Event, EventCategory, EventLocation, EventOccurrence, EventSource, EventTag, EventfrogOccurrenceLink

CATEGORY_NAMES = {
    'festival':'お祭り・フェス', 'market':'マーケット', 'art':'アート',
    'museum':'博物館・展示', 'music':'音楽', 'theater':'演劇', 'food':'グルメ',
    'workshop':'体験・ワークショップ', 'family':'親子・家族',
    'nature':'自然', 'sports':'スポーツ', 'other':'その他',
}
TAG_NAMES = {'family':'家族向け','children':'子ども向け','baby':'赤ちゃん','japan':'日本関連','weekend':'週末'}
TIERS = {'featured','standard','compact'}


def as_datetime(raw):
    try:
        obj = datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return None
    return obj if timezone.is_aware(obj) else None


class Command(BaseCommand):
    help = 'Import selected.json as published Eventfrog events. DRY RUN unless --commit.'

    def add_arguments(self, parser):
        parser.add_argument('--file', default='outings_ai_data/selected.json')
        parser.add_argument('--commit', action='store_true', help='Create/update and publish Eventfrog events in this database')

    def handle(self, *args, **opts):
        path = Path(opts['file'])
        if not path.is_file():
            raise CommandError(f'No selected JSON: {path}')
        try:
            items = json.loads(path.read_text(encoding='utf-8-sig'))
        except (ValueError, UnicodeError) as exc:
            raise CommandError(f'Invalid JSON: {exc}')
        if not isinstance(items, list):
            raise CommandError('Expected a JSON list')
        cleaned = []
        seen_ids = set()
        for index, item in enumerate(items, 1):
            ai = item.get('ai') if isinstance(item, dict) else None
            if not isinstance(ai, dict):
                raise CommandError(f'Row {index}: missing ai')
            eid = str(item.get('id') or '').strip()
            tier = str(item.get('listing_tier') or '')
            starts = [(o, as_datetime(o.get('start'))) for o in item.get('occurrences', []) if isinstance(o, dict)]
            valid_dates = [(o, dt) for o, dt in starts if dt and (not as_datetime(o.get('end')) or as_datetime(o.get('end')) >= dt)]
            url = str(item.get('url') or '')
            parsed = urlparse(url)
            
            # Reject mismatched Eventfrog URLs.
            # A wrong article URL must never be saved.

            url_event_id = re.search(
                r"-(\d+)\.html$",
                parsed.path,
            )

            allowed_ids = {
                eid,
                *(
                    str(o.get("id"))
                    for o in item.get("occurrences", [])
                    if isinstance(o, dict) and o.get("id")
                ),
            }

            if (
                not url_event_id
                or url_event_id.group(1) not in allowed_ids
            ):
                raise CommandError(
                    f"Row {index}: Eventfrog URL does not match event ID {eid}"
                )
            if not eid or eid in seen_ids or tier not in TIERS or not valid_dates or not ai.get('title_ja') or not item.get('region') or not item.get('city') or not item.get('venue') or parsed.scheme != 'https' or parsed.hostname not in ('eventfrog.ch', 'www.eventfrog.ch'):
                raise CommandError(f'Row {index}: incomplete or duplicate entry: {eid}')
            seen_ids.add(eid)
            cleaned.append((item, ai, valid_dates))
        self.stdout.write(f'Validated: {len(cleaned)} curated events; mode={"PUBLISH IMPORT" if opts["commit"] else "DRY RUN"}')
        if not opts['commit']:
            self.stdout.write('No DB changes. Pass --commit to create/update PUBLISHED Eventfrog events in this DB.')
            return
        created_count = updated_count = skipped_count = 0
        claimed_event_ids = set()
        with transaction.atomic():
            source, _ = EventSource.objects.get_or_create(name='Eventfrog', defaults={'website_url':'https://eventfrog.ch/'})
            for item, ai, valid_dates in cleaned:
                slug = str(ai.get('category') or 'other')
                if slug not in CATEGORY_NAMES:
                    slug = 'other'
                category, _ = EventCategory.objects.get_or_create(slug=slug, defaults={'name':CATEGORY_NAMES[slug]})
                venue = str(item['venue']).strip()[:200]
                city = str(item['city']).strip()[:120]
                canton = str(item['region']).strip()[:10]
                location, _ = EventLocation.objects.get_or_create(name=venue, city=city, canton=canton, address='', defaults={})
                eid = str(item['id'])
                # Previously imported occurrences can already belong to a different
                # representative ID after the editorial deduplication changes.
                # Reuse their existing Event rather than creating a duplicate.
                occurrence_ids = {
                    str(o.get('id')).strip() for o, _ in valid_dates
                    if o.get('id') not in (None, '')
                }
                owner_ids = set(EventfrogOccurrenceLink.objects.filter(
                    eventfrog_id__in=occurrence_ids
                ).values_list('event_id', flat=True))
                by_external_id = Event.objects.filter(source=source, external_id=eid).first()
                if len(owner_ids) > 1:
                    self.stderr.write(f'SKIP {eid}: occurrences already linked to multiple Event records {sorted(owner_ids)}. Manual review required.')
                    skipped_count += 1
                    continue
                if owner_ids:
                    owner_id = next(iter(owner_ids))
                    existing = Event.objects.filter(pk=owner_id, source=source).first()
                    if existing is None or (by_external_id and by_external_id.pk != owner_id):
                        self.stderr.write(f'SKIP {eid}: ambiguous owner / representative ID. Manual review required.')
                        skipped_count += 1
                        continue
                else:
                    existing = by_external_id
                if existing and existing.pk in claimed_event_ids:
                    self.stderr.write(f'SKIP {eid}: another selected row already used Event {existing.pk}.')
                    skipped_count += 1
                    continue
                if existing and existing.status not in (Event.Status.DRAFT, Event.Status.PUBLISHED):
                    # Respect manual cancellation, rejection, and pending review.
                    self.stdout.write(f'Skipped event with protected status {eid}: {existing.status}')
                    continue
                image = str(item.get('image_url') or '').strip()
                if urlparse(image).scheme != 'https':
                    image = ''
                lang = str(ai.get('language_barrier') or 'unknown')
                allowed_lang = {x for x, _ in Event.LanguageBarrier.choices}
                if lang not in allowed_lang:
                    lang = 'unknown'
                defaults = {
                    'title':str(ai['title_ja']).strip()[:250],
                    'title_original':str(item.get('title') or '')[:250],
                    'summary_ja':str(ai.get('summary_ja') or ''),
                    'description_original':str(item.get('description') or ''),
                    'listing_tier':str(item['listing_tier']),
                    'event_type':Event.EventType.LONG_RUNNING if item.get('is_long_running') else (Event.EventType.RECURRING if len(valid_dates)>1 else Event.EventType.ONE_TIME),
                    'status':Event.Status.PUBLISHED,
                    'category':category, 'location':location, 'language_barrier':lang,
                    'original_url':url, 'image_url':image, 'ai_processed_at':timezone.now(),
                }
                if existing:
                    event = existing
                    for k,v in defaults.items():
                        setattr(event,k,v)
                    event.save()
                    updated_count += 1
                else:
                    event = Event.objects.create(source=source, external_id=eid, **defaults)
                    created_count += 1
                claimed_event_ids.add(event.pk)
                tag_slugs = {t for t in ai.get('tags', []) if isinstance(t, str) and t in TAG_NAMES}
                tags = [EventTag.objects.get_or_create(slug=t, defaults={'name':TAG_NAMES[t]})[0] for t in sorted(tag_slugs)]
                event.tags.set(tags)
                # Keep existing occurrence PKs, comments and hearts intact; upsert by start time.
                for occurrence, start in valid_dates:
                    end = as_datetime(occurrence.get('end'))
                    obj, _ = EventOccurrence.objects.update_or_create(event=event, start_at=start, defaults={'end_at':end, 'is_cancelled':False})
                    occurrence_id = str(occurrence.get('id') or '').strip()
                    if occurrence_id:
                        link = EventfrogOccurrenceLink.objects.filter(eventfrog_id=occurrence_id).first()
                        if link is None:
                            EventfrogOccurrenceLink.objects.create(eventfrog_id=occurrence_id, event=event, occurrence=obj, last_source_start_at=start)
                        elif link.event_id == event.pk:
                            link.occurrence = obj
                            link.last_source_start_at = start
                            link.save(update_fields=['occurrence','last_source_start_at','last_seen_at'])
                        else:
                            # Safeguard against a concurrent data change. Roll back
                            # rather than silently transferring linked event IDs.
                            raise CommandError(f'Occurrence ownership changed during import: {occurrence_id}')
        self.stdout.write(self.style.SUCCESS(f'Imported published Eventfrog events: created={created_count} updated={updated_count} skipped={skipped_count}.'))
