"""Daily Eventfrog curation. New public events capped at 15 per run.

Dry run does not fetch external APIs or spend AI tokens.
--commit performs collection, bounded AI screening, and import.
AI assessments are cached in the Django DB, not in ephemeral JSON files.
"""
import json
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from outings.models import Event, EventSource, EventfrogOccurrenceLink, EventfrogTranslationCache
from outings.services.eventfrog import collect, enrich_locations, group
from outings.services.ai_editor import evaluate, editorial_key
from outings.services.selector import select
from outings.services.candidate_ranker import rank_daily_candidates
from outings.services.eventfrog_existing_sync import sync_existing


class Command(BaseCommand):
    help = 'Curate up to 15 NEW Eventfrog events and publish them. Dry-run by default.'

    def add_arguments(self, parser):
        parser.add_argument('--commit', action='store_true', help='Call external APIs, spend AI requests, and publish events')
        parser.add_argument('--max-new', type=int, default=15)
        parser.add_argument('--max-ai', type=int, default=40, help='Maximum NEW paid AI calls per run')
        parser.add_argument('--pages', type=int, default=20)
        parser.add_argument('--days', type=int, default=30)
        parser.add_argument('--model', default='gpt-4.1-mini')
        parser.add_argument('--cleanup', action='store_true', help='Also unpublish ended Eventfrog events after successful import')

    def handle(self, *args, **opts):
        if not 1 <= opts['max_new'] <= 15:
            raise CommandError('--max-new must be between 1 and 15')
        if not 0 <= opts['max_ai'] <= 100:
            raise CommandError('--max-ai must be between 0 and 100')
        if not 1 <= opts['pages'] <= 60 or not 1 <= opts['days'] <= 90:
            raise CommandError('--pages 1..60; --days 1..90 required')
        if not opts['commit']:
            self.stdout.write('DRY RUN: no Eventfrog/OpenAI requests, no DB changes.')
            self.stdout.write(f"Configured: max-new={opts['max_new']}, max-ai={opts['max_ai']}, pages={opts['pages']}, days={opts['days']}, cleanup={opts['cleanup']}")
            return

        from django.conf import settings
        base = Path(settings.BASE_DIR)
        data_dir = base / 'outings_ai_data'
        data_dir.mkdir(exist_ok=True)
        locations_cache = data_dir / 'locations.json'
        self.stdout.write('Fetching Eventfrog events...', ending='\n')
        raw = collect(pages=opts['pages'], days=opts['days'])
        changed = sync_existing(raw, commit=True)
        self.stdout.write(f"Existing Eventfrog occurrences: {changed}")
        located = enrich_locations(raw, cache_file=locations_cache)
        grouped = group(located)
        self.stdout.write(f'Candidates: {len(grouped)} grouped, {len(located)} located')

        # Filter using all known occurrence IDs, not only representative IDs.
        occurrence_ids = {str(o.get('id')) for e in grouped for o in e.get('occurrences', []) if o.get('id')}
        linked_ids = set(EventfrogOccurrenceLink.objects.filter(eventfrog_id__in=occurrence_ids).values_list('eventfrog_id', flat=True))
        source_ids = set(Event.objects.filter(source__name__iexact='Eventfrog', external_id__in=[str(e.get('id')) for e in grouped]).values_list('external_id', flat=True))
        unseen = []
        for event in grouped:
            ids = {str(o.get('id')) for o in event.get('occurrences', []) if o.get('id')}
            if (ids & linked_ids) or str(event.get('id')) in source_ids:
                continue
            unseen.append(event)

        # Rank before paid AI calls. Balance region and dates, and reject only
        # unambiguous reservation-only / closed corporate offers.
        now = timezone.now()
        ordered, rejected = rank_daily_candidates(unseen, now=now)
        self.stdout.write(
            f'Pre-AI: unseen={len(unseen)}, eligible={len(ordered)}, '
            f'rejected={sum(rejected.values())}, reasons={rejected}'
        )
        self.stdout.write(
            'Top candidate preview: '
            + ' | '.join(str(e.get('title', ''))[:45] for e in ordered[:8])
        )

        evaluated = []
        paid = 0
        for event in ordered:
            key = editorial_key(event, opts['model'])
            cache = EventfrogTranslationCache.objects.filter(series_key=key).first()
            if cache:
                ai = (cache.row_data or {}).get('ai')
                if not isinstance(ai, dict):
                    self.stderr.write(f'Skipping invalid DB AI cache record: {key}')
                    continue
            else:
                if paid >= opts['max_ai']:
                    break
                self.stdout.write(f'AI evaluating {paid + 1}/{opts["max_ai"]}: {str(event.get("title", ""))[:65]}')
                try:
                    ai = evaluate(event, model=opts['model'])
                except Exception as exc:
                    self.stderr.write(f'AI evaluation stopped: {exc}')
                    break
                # Save each paid result immediately; safe across Cron restarts.
                EventfrogTranslationCache.objects.update_or_create(
                    series_key=key,
                    defaults={
                        'title_ja': str(ai.get('title_ja') or event['title'])[:250],
                        'summary_ja': str(ai.get('summary_ja') or ''),
                        'row_data': {'ai': ai, 'model': opts['model'], 'source': 'daily_outings'},
                    },
                )
                paid += 1
            evaluated.append({**event, 'ai': ai})

        selected = select(evaluated, target=opts['max_new'], now=now, days=opts['days'])
        self.stdout.write(f'New events selected={len(selected)} from evaluated={len(evaluated)}; new paid evaluations={paid}')
        if selected:
            # The existing importer already implements identity resolution, link preservation,
            # published status and atomic writes. Reuse it exactly.
            with tempfile.TemporaryDirectory(prefix='yapp-outings-') as tmp:
                filename = Path(tmp) / 'selected.json'
                filename.write_text(json.dumps(selected, ensure_ascii=False), encoding='utf-8')
                call_command('import_outings_selected', file=str(filename), commit=True)
        if opts['cleanup']:
            call_command('cleanup_outings', commit=True)
        self.stdout.write(self.style.SUCCESS('Daily run finished.'))
