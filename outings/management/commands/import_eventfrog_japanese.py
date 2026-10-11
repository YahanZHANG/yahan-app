"""Import Eventfrog Japanese events; optionally publish those passing automated checks.

Dry-run:
 python manage.py import_eventfrog_japanese --file outings_audit/eventfrog_japanese_draft_review.csv --auto-publish
Commit:
 python manage.py import_eventfrog_japanese --file outings_audit/eventfrog_japanese_draft_review.csv --auto-publish --commit

NOTE: Checks are structural, NOT verification of original event-page facts.
"""
import csv
import hashlib
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from outings.models import Event, EventLocation, EventOccurrence, EventSource

TZ = ZoneInfo('Europe/Zurich')
VALID_REGIONS = {'ZH', 'AG', 'BE', 'BS', 'BL', 'LU', 'ZG'}


def dates(text):
    values = []
    for part in (text or '').split('|'):
        part = part.strip()
        if not part:
            continue
        dt = datetime.fromisoformat(part.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            raise ValueError('timezone missing')
        values.append(dt.astimezone(TZ))
    return sorted(set(values))


def official_eventfrog_url(url):
    try:
        u = urlsplit(url.strip())
        return (u.scheme == 'https'
                and u.hostname in ('eventfrog.ch', 'www.eventfrog.ch')
                and u.path.startswith('/'))
    except ValueError:
        return False


def validate(row, now):
    reasons = []
    for name in ('title', 'title_ja', 'summary_ja', 'city', 'venue',
                 'event_url', 'series_key', 'occurrence_starts'):
        if not (row.get(name) or '').strip():
            reasons.append(f'{name} missing')
    if (row.get('region') or '').strip().upper() not in VALID_REGIONS:
        reasons.append('unsupported or unknown region')
    if not official_eventfrog_url(row.get('event_url') or ''):
        reasons.append('invalid Eventfrog URL')
    if not (row.get('title_ja') or '').strip() or not (row.get('summary_ja') or '').strip():
        reasons.append('Japanese content missing')
    try:
        starts = [dt for dt in dates(row.get('occurrence_starts')) if dt >= now]
    except (ValueError, TypeError) as exc:
        reasons.append(f'invalid start time: {exc}')
        starts = []
    if not starts:
        reasons.append('no future start dates')
    return starts, reasons


class Command(BaseCommand):
    help = 'Import Japanese Eventfrog events; --auto-publish publishes structurally valid rows.'

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True)
        parser.add_argument('--commit', action='store_true')
        parser.add_argument('--auto-publish', action='store_true')

    def handle(self, *args, **opts):
        p = Path(opts['file'])
        if not p.is_file():
            raise CommandError(f'CSV file not found: {p}')
        if not EventOccurrence._meta.get_field('end_at').null:
            raise CommandError('EventOccurrence.end_at must allow NULL. Do not invent end times.')
        with p.open(encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f))
        if not rows:
            raise CommandError('CSV is empty')

        now = timezone.now()
        prepared = []
        held = []
        for line_no, row in enumerate(rows, start=2):
            # Manual import still requires explicit CSV approval.
            if not opts['auto_publish'] and (row.get('review_status') or '').strip() != 'APPROVED_FOR_DRAFT':
                continue
            starts, reasons = validate(row, now)
            if reasons:
                held.append((line_no, row.get('title_ja') or row.get('title') or '', reasons))
                continue
            stable_id = 'series-' + hashlib.sha256(row['series_key'].encode('utf-8')).hexdigest()[:32]
            prepared.append((row, starts, stable_id))

        mode = 'AUTO-PUBLISH' if opts['auto_publish'] else 'DRAFT'
        self.stdout.write(f'Mode: {mode}, rows eligible: {len(prepared)}, held: {len(held)}')
        for row, starts, _ in prepared:
            self.stdout.write(f'  {row["region"]} {row["title_ja"]} / {len(starts)} start(s)')
        for line, title, reasons in held:
            self.stdout.write(self.style.WARNING(f'  HOLD line {line}: {title} — {"; ".join(reasons)}'))
        if not opts['commit']:
            self.stdout.write('DRY RUN: no database changes. Add --commit to execute.')
            return

        created_count = updated_count = occurrence_count = published_count = 0
        with transaction.atomic():
            source, _ = EventSource.objects.get_or_create(
                name='Eventfrog', defaults={'website_url': 'https://eventfrog.ch/', 'is_active': True}
            )
            for row, starts, stable_id in prepared:
                location, _ = EventLocation.objects.get_or_create(
                    name=row['venue'].strip(), city=row['city'].strip(),
                    canton=row['region'].strip().upper(),
                )
                event, created = Event.objects.get_or_create(
                    source=source,
                    external_id=stable_id,
                    defaults={
                        'title': row['title_ja'].strip(),
                        'title_original': row['title'].strip(),
                        'summary_ja': row['summary_ja'].strip(),
                        'description_original': row.get('description', ''),
                        'event_type': Event.EventType.ONE_TIME,
                        'status': Event.Status.DRAFT,
                        'location': location,
                        'original_url': row['event_url'].strip(),
                        'is_free': False,  # Unknown is not claimed to be free.
                        'price_text': '料金・申込条件は公式ページで確認',
                    },
                )
                if created:
                    created_count += 1
                elif event.status != Event.Status.DRAFT and event.status != Event.Status.PUBLISHED:
                    # A manually held status must not be overridden by the importer.
                    self.stdout.write(self.style.WARNING(f'SKIP manually held event: {event.title}'))
                    continue
                else:
                    updated_count += 1
                # Do not overwrite title/description edited in Django Admin.
                for start in starts:
                    _, added = EventOccurrence.objects.get_or_create(
                        event=event, start_at=start,
                        defaults={'end_at': None, 'is_cancelled': False},
                    )
                    occurrence_count += int(added)
                if opts['auto_publish'] and event.status == Event.Status.DRAFT:
                    event.status = Event.Status.PUBLISHED
                    event.save(update_fields=['status'])
                    published_count += 1
        self.stdout.write(self.style.SUCCESS(
            f'Created: {created_count}; existing: {updated_count}; new dates: {occurrence_count}; '
            f'newly published: {published_count}; held rows: {len(held)}'
        ))
        self.stdout.write('Note: URL/domain and data shape checked, not live availability or source factual accuracy.')
