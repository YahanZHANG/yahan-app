"""Eventfrog 40 x 1000 scan -> current 45-day snapshot -> quality gate -> JP -> publish.

Save as outings/management/commands/sync_eventfrog_outings.py

Dry run (live Eventfrog, no OpenAI/DB):
    python manage.py sync_eventfrog_outings
Offline dry run on existing CSVs:
    python manage.py sync_eventfrog_outings --offline \
        --input outings_audit/eventfrog_future_events_p1_to_p20.csv \
        --input outings_audit/eventfrog_future_events_p21_to_p30.csv
Live publish (uses paid OpenAI):
    python manage.py sync_eventfrog_outings --commit

Important: no cancellation reconciliation; human edits are not overwritten by importer.
"""
import csv
import importlib
from collections import Counter
from datetime import timedelta
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .eventfrog_quality import evaluate

OUT = Path('outings_audit')
SNAPSHOT = OUT / 'eventfrog_current_45days.csv'
TRANSLATED = OUT / 'eventfrog_japanese_batch.csv'
PASS_ONLY = OUT / 'eventfrog_japanese_autopublish_pass.csv'
REVIEW = OUT / 'eventfrog_review_queue.csv'


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path, fields, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def aware_date(value):
    dt = parse_datetime(value or '')
    if dt is None or timezone.is_naive(dt):
        return None
    return dt


class Command(BaseCommand):
    help = 'Eventfrog snapshot (40x1000), 45-day filter, PASS-only AI translation and publication.'

    def add_arguments(self, parser):
        parser.add_argument('--commit', action='store_true', help='Use paid OpenAI API and update database')
        parser.add_argument('--offline', action='store_true', help='Use --input CSVs and cached venue data only')
        parser.add_argument('--input', action='append', default=[], help='Offline scan CSV; can repeat')
        parser.add_argument('--pages', type=int, default=40)
        parser.add_argument('--per-page', type=int, default=1000)
        parser.add_argument('--days', type=int, default=45)
        parser.add_argument('--limit', type=int, default=10, help='Max AI translations per run')
        parser.add_argument('--model', default='gpt-4.1-mini')

    def handle(self, *args, **opts):
        if not 1 <= opts['pages'] <= 60:
            raise CommandError('--pages must be 1..60')
        if not 1 <= opts['per_page'] <= 1000:
            raise CommandError('--per-page must be 1..1000')
        if not 1 <= opts['days'] <= 90:
            raise CommandError('--days must be 1..90')
        if not 1 <= opts['limit'] <= 30:
            raise CommandError('--limit must be 1..30')
        if opts['offline'] and not opts['input']:
            raise CommandError('--offline requires explicit --input CSV(s) to prevent stale data mixing')
        if opts['input'] and not opts['offline']:
            raise CommandError('--input is only allowed with --offline')
        OUT.mkdir(parents=True, exist_ok=True)
        # Freeze a consistent horizon for THIS execution. Do not use old CSVs implicitly.
        now = timezone.now()
        horizon = now + timedelta(days=opts['days'])

        self.stdout.write('1/5 Scan Eventfrog / select this run only')
        if opts['offline']:
            files = [Path(p) for p in opts['input']]
        else:
            # The scan command writes a uniquely determined filename, and overwrites that
            # filename each run. Avoid accidentally reading previous runs' other files.
            files = [OUT / f'eventfrog_future_events_p1_to_p{opts["pages"]}.csv']
            # Clear this precise output first so a failed scan cannot reuse a stale snapshot.
            if files[0].exists():
                files[0].unlink()
            call_command('scan_eventfrog_future', start_page=1, max_pages=opts['pages'],
                         per_page=opts['per_page'], days=opts['days'])
        for path in files:
            if not path.is_file():
                raise CommandError(f'Scan file not found: {path}')

        # Enforce the fixed horizon before venue lookup and translation.
        by_id = {}
        input_count = 0
        for path in files:
            fields, rows = read_csv(path)
            required = {'id', 'begin', 'end', 'location_ids', 'title'}
            if not required.issubset(fields):
                raise CommandError(f'Unexpected scan CSV format: {path}: missing {required - set(fields)}')
            for row in rows:
                input_count += 1
                start = aware_date(row.get('begin'))
                end = aware_date(row.get('end'))
                if not start or not end or end <= now or not (now <= start <= horizon):
                    continue
                if str(row.get('cancelled', '')).lower() == 'true':
                    continue
                if str(row.get('visible', '')).lower() == 'false':
                    continue
                if str(row.get('published', '')).lower() == 'false':
                    continue
                if row.get('id'):
                    by_id[str(row['id'])] = row
        if not by_id:
            raise CommandError('No eligible event IDs in this snapshot. No DB changes made.')
        write_csv(SNAPSHOT, fields, list(by_id.values()))
        last_start = max(aware_date(r['begin']) for r in by_id.values())
        self.stdout.write(f'Snapshot: {len(by_id)} unique events from {input_count} rows; '
                          f'last start: {timezone.localtime(last_start):%Y-%m-%d %H:%M}; '
                          f'45-day horizon: {timezone.localtime(horizon):%Y-%m-%d %H:%M}')
        if last_start < horizon - timedelta(days=2):
            self.stdout.write(self.style.WARNING('WARNING: scan may not reach the desired horizon. Increase --pages if needed.'))

        self.stdout.write('2/5 Resolve regions / consolidate provisional series')
        organizer = importlib.import_module('outings.management.commands.organize_eventfrog_regions')
        previous_inputs = organizer.INPUT_FILES
        # Limit organizer to the freshly written snapshot; never glob historical CSVs.
        organizer.INPUT_FILES = [SNAPSHOT]
        try:
            call_command('organize_eventfrog_regions', offline=opts['offline'])
        finally:
            organizer.INPUT_FILES = previous_inputs

        self.stdout.write('3/5 Prepare review candidates')
        call_command('prepare_eventfrog_review')

        self.stdout.write('4/5 Quality filter + JP translation of new PASS rows')
        call_command('translate_eventfrog_batch', limit=opts['limit'], quality_filter=True,
                     commit=opts['commit'], model=opts['model'])
        if not TRANSLATED.is_file():
            self.stdout.write('No translated events yet. Finished without publishing.')
            return

        # Whitelist against CURRENT snapshot and refresh structural information in translated rows.
        # This prevents stale, previously translated but now missing candidates from being republished.
        _, current_rows = read_csv(REVIEW)
        current_by_key = {r['series_key']: r for r in current_rows if r.get('series_key')}
        fields, translated_rows = read_csv(TRANSLATED)
        pass_rows = []
        counts = Counter()
        for old in translated_rows:
            current = current_by_key.get(old.get('series_key', ''))
            if current is None:
                counts['STALE_OR_NOT_IN_SNAPSHOT'] += 1
                continue
            decision, _reason = evaluate(current)
            counts[decision] += 1
            if decision != 'PASS':
                continue
            # Refresh dates, original URL and venue from current scan, keep approved JA translation.
            merged = dict(old)
            merged.update(current)
            merged['title_ja'] = old.get('title_ja', '')
            merged['summary_ja'] = old.get('summary_ja', '')
            merged['review_status'] = 'AI_TRANSLATED_UNVERIFIED'
            pass_rows.append(merged)
        write_csv(PASS_ONLY, fields, pass_rows)
        self.stdout.write(f'Current translated PASS: {len(pass_rows)}; '
                          f'held={counts["HOLD"]}, skipped={counts["SKIP"]}, '
                          f'outdated/outside snapshot={counts["STALE_OR_NOT_IN_SNAPSHOT"]}')

        self.stdout.write('5/5 Publish PASS only')
        if pass_rows:
            call_command('import_eventfrog_japanese', file=str(PASS_ONLY),
                         auto_publish=True, commit=opts['commit'])
        else:
            self.stdout.write('No matching translated PASS rows; import skipped.')
        self.stdout.write(self.style.SUCCESS(
            'Finished. ' + ('DB updated, OpenAI used for new items.' if opts['commit']
                            else 'Dry-run: no DB changes or OpenAI calls.')
        ))
        self.stdout.write('Note: this version does not reconcile cancellations or updates to already published events.')
