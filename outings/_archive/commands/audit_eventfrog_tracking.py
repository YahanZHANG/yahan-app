"""Read-only diagnosis of Eventfrog matching and cancellation data.

Save as outings/management/commands/audit_eventfrog_tracking.py
"""
import csv
import hashlib
from collections import Counter
from pathlib import Path
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from outings.models import Event, EventSource, EventfrogOccurrenceLink

UTC = ZoneInfo('UTC')


def load_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def parse_aware(value):
    dt = parse_datetime(str(value or '').strip())
    return dt.astimezone(UTC) if dt and timezone.is_aware(dt) else None


def yes(value):
    return str(value or '').strip().lower() in ('true', 'yes', '1')


class Command(BaseCommand):
    help = 'Read-only audit of Eventfrog ID matching, cancellations and source dates.'

    def add_arguments(self, parser):
        parser.add_argument('--review', default='outings_audit/eventfrog_review_queue.csv')
        parser.add_argument('--snapshot', default='outings_audit/eventfrog_future_events_p1_to_p40.csv')
        parser.add_argument('--examples', type=int, default=12)

    def handle(self, *args, **options):
        review_path = Path(options['review'])
        scan_path = Path(options['snapshot'])
        if not review_path.is_file() or not scan_path.is_file():
            raise CommandError('CSV missing. Supply --review and --snapshot.')
        review = load_csv(review_path)
        snapshot = load_csv(scan_path)
        raw_by_id = {str(r.get('id') or '').strip(): r for r in snapshot if r.get('id')}
        if not raw_by_id:
            raise CommandError('No Eventfrog IDs in snapshot.')
        source = EventSource.objects.filter(name='Eventfrog').first()
        if source is None:
            raise CommandError('Eventfrog source not found in DB.')

        keys = {
            'series-' + hashlib.sha256(str(r.get('series_key')).encode()).hexdigest()[:32]: r
            for r in review if r.get('series_key')
        }
        events = Event.objects.filter(source=source, external_id__in=keys).prefetch_related('occurrences')
        counts = Counter()
        samples = []
        total_links = EventfrogOccurrenceLink.objects.count()
        known_links = dict(EventfrogOccurrenceLink.objects.filter(eventfrog_id__in=raw_by_id).values_list('eventfrog_id', 'occurrence_id'))
        raw_cancelled = sum(yes(r.get('cancelled')) for r in snapshot)
        raw_invisible = sum(str(r.get('visible') or '').lower() == 'false' for r in snapshot)

        for event in events:
            row = keys[event.external_id]
            local_starts = {o.start_at.astimezone(UTC) for o in event.occurrences.all()}
            for external_id in (x.strip() for x in str(row.get('event_ids') or '').split('|') if x.strip()):
                raw = raw_by_id.get(external_id)
                if raw is None:
                    label = 'source_ID_missing_from_snapshot'
                    source_start = None
                else:
                    source_start = parse_aware(raw.get('begin'))
                    if source_start is None:
                        label = 'invalid_source_start'
                    elif external_id in known_links:
                        label = 'already_linked'
                    elif source_start in local_starts:
                        label = 'exact_start_match_unlinked'
                    else:
                        label = 'no_matching_local_start'
                counts[label] += 1
                if label != 'already_linked' and len(samples) < max(0, options['examples']):
                    samples.append((label, event.pk, event.title, external_id,
                                    str(source_start) if source_start else '-',
                                    ', '.join(str(d) for d in sorted(local_starts)[:3])))

        tracked_ids = set(EventfrogOccurrenceLink.objects.values_list('eventfrog_id', flat=True))
        self.stdout.write(f'Snapshot rows: {len(snapshot)} / distinct IDs: {len(raw_by_id)}')
        self.stdout.write(f'Explicit cancelled=true in snapshot: {raw_cancelled}')
        self.stdout.write(f'Explicit visible=false in snapshot: {raw_invisible}')
        self.stdout.write(f'DB tracked Eventfrog IDs: {total_links}; present in snapshot: {len(tracked_ids & set(raw_by_id))}')
        for category, count in sorted(counts.items()):
            self.stdout.write(f'  {category}: {count}')
        self.stdout.write('Examples (status | event PK | title | Eventfrog ID | source UTC | local UTC first 3):')
        for sample in samples:
            self.stdout.write('  ' + ' | '.join(map(str, sample)))
        self.stdout.write('READ ONLY: database unchanged; no external APIs or OpenAI calls.')
