"""Daily Eventfrog curation: collect, screen with AI, write articles, publish.

Dry run (default) does not call Eventfrog or OpenAI.
--commit runs the whole pipeline. AI results are cached in the DB
(EventfrogTranslationCache), so a rerun on the same day costs almost nothing.

A failure in one step or one event is logged and the run continues; the
command still exits with an error at the end so the scheduler can alert.
"""
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from outings.models import Event, EventfrogOccurrenceLink, EventfrogTranslationCache
from outings.services import ai_editor
from outings.services.candidate_ranker import rank_daily_candidates
from outings.services.eventfrog import collect_snapshot, enrich_locations, group
from outings.services.eventfrog_daily_images import upload_images_for_selected
from outings.services.eventfrog_existing_sync import apply_cancellations, sync_existing
from outings.services.importer import import_items
from outings.services.selector import select

SCREEN_BATCH = 35


def data_dir():
    """Next to the SQLite file, i.e. on Render's persistent disk."""
    path = Path(settings.DATABASES['default']['NAME']).parent / 'outings_ai_data'
    path.mkdir(parents=True, exist_ok=True)
    return path


def cached(key):
    row = EventfrogTranslationCache.objects.filter(series_key=key).first()
    return (row.row_data or {}) if row else None


def store(key, title, summary, data):
    EventfrogTranslationCache.objects.update_or_create(
        series_key=key,
        defaults={'title_ja': str(title or '')[:250], 'summary_ja': str(summary or ''), 'row_data': data},
    )


class Command(BaseCommand):
    help = 'Curate up to 15 NEW Eventfrog events and publish them. Dry-run by default.'

    def add_arguments(self, parser):
        parser.add_argument('--commit', action='store_true', help='Call Eventfrog and OpenAI, and publish events')
        parser.add_argument('--max-new', type=int, default=15)
        parser.add_argument('--max-screen', type=int, default=500, help='Maximum NEW candidates screened by AI per run')
        parser.add_argument('--pages', type=int, default=30)
        parser.add_argument('--days', type=int, default=30)
        parser.add_argument('--cleanup', action='store_true', help='Also unpublish ended Eventfrog events and delete past events')
        parser.add_argument('--images', action='store_true', help='Upload images of new events to Cloudinary')

    def handle(self, *args, **opts):
        if not 1 <= opts['max_new'] <= 30:
            raise CommandError('--max-new must be between 1 and 30')
        if not 0 <= opts['max_screen'] <= 3000:
            raise CommandError('--max-screen must be between 0 and 3000')
        if not 1 <= opts['pages'] <= 60 or not 1 <= opts['days'] <= 90:
            raise CommandError('--pages 1..60; --days 1..90 required')
        if not opts['commit']:
            self.stdout.write('DRY RUN: no Eventfrog/OpenAI requests, no DB changes.')
            self.stdout.write(f'Configured: {opts}')
            return

        self.errors = []
        now = timezone.now()

        self.stdout.write('Fetching Eventfrog events...')
        raw, cancelled = collect_snapshot(pages=opts['pages'], days=opts['days'])
        self.step('date sync', lambda: sync_existing(raw, commit=True))
        self.step('cancellations', lambda: apply_cancellations(cancelled, commit=True))

        located = enrich_locations(raw, cache_file=data_dir() / 'locations.json')
        grouped = group(located)
        unseen = self.unseen(grouped)
        ordered, rejected = rank_daily_candidates(unseen, now=now)
        self.stdout.write(f'Candidates: grouped={len(grouped)}, unseen={len(unseen)}, eligible={len(ordered)}, rejected={rejected}')

        screened = self.screen(ordered, now=now, limit=opts['max_screen'])
        picks = select(screened, target=opts['max_new'] * 2, now=now, days=opts['days'])
        selected = self.write_articles(picks, now=now, limit=opts['max_new'])
        self.stdout.write(f'Selected {len(selected)} from {len(screened)} screened candidates')

        if selected:
            self.step('import', lambda: import_items(selected, log=self.stdout.write, warn=self.stderr.write))
            if opts['images']:
                self.step('images', lambda: upload_images_for_selected(selected, raw, max_uploads=opts['max_new']))
        if opts['cleanup']:
            self.step('cleanup', lambda: call_command('cleanup_outings', commit=True))

        if self.errors:
            raise CommandError('Daily run finished with errors: ' + '; '.join(self.errors))
        self.stdout.write(self.style.SUCCESS('Daily run finished.'))

    def step(self, name, func):
        try:
            result = func()
        except Exception as exc:
            self.errors.append(f'{name}: {type(exc).__name__}: {exc}')
            self.stderr.write(f'ERROR {name}: {type(exc).__name__}: {exc}')
            return None
        if result is not None:
            self.stdout.write(f'{name}: {result}')
        return result

    def unseen(self, grouped):
        """Drop programmes already imported under any of their occurrence IDs."""
        occurrence_ids = {str(o.get('id')) for e in grouped for o in e.get('occurrences', []) if o.get('id')}
        linked = set(EventfrogOccurrenceLink.objects.filter(eventfrog_id__in=occurrence_ids).values_list('eventfrog_id', flat=True))
        known = set(Event.objects.filter(
            source__name__iexact='Eventfrog', external_id__in=[str(e.get('id')) for e in grouped],
        ).values_list('external_id', flat=True))
        return [
            e for e in grouped
            if not ({str(o.get('id')) for o in e.get('occurrences', [])} & linked) and str(e.get('id')) not in known
        ]

    def screen(self, ordered, *, now, limit):
        model = ai_editor.model_name()
        screened, pending = [], []
        for event in ordered:
            hit = cached(ai_editor.screen_key(event, model))
            if hit and isinstance(hit.get('screen'), dict):
                screened.append({**event, 'screen': hit['screen']})
            elif len(pending) < limit:
                pending.append(event)
        self.stdout.write(f'Screening: cached={len(screened)}, new={len(pending)}')
        failures = 0
        for start in range(0, len(pending), SCREEN_BATCH):
            batch = pending[start:start + SCREEN_BATCH]
            try:
                results = ai_editor.screen_batch(batch, now=now, model=model)
            except ai_editor.AIError as exc:
                failures += 1
                self.stderr.write(f'Screening batch failed: {exc}')
                if failures >= 3:
                    self.errors.append(f'screening stopped after {failures} failed batches: {exc}')
                    break
                continue
            for event in batch:
                result = results.get(str(event['id']))
                if result is None:
                    continue
                store(ai_editor.screen_key(event, model), event.get('title'), '', {'screen': result, 'model': model})
                screened.append({**event, 'screen': result})
            self.stdout.write(f'Screened {min(start + SCREEN_BATCH, len(pending))}/{len(pending)}')
        return screened

    def write_articles(self, picks, *, now, limit):
        model = ai_editor.model_name('article')
        selected = []
        for event in picks:
            if len(selected) >= limit:
                break
            key = ai_editor.article_key(event, model)
            hit = cached(key)
            article = hit.get('article') if hit else None
            if not isinstance(article, dict):
                try:
                    article = ai_editor.write_article(event, now=now, model=model)
                except ai_editor.AIError as exc:
                    self.stderr.write(f'Article skipped for {event.get("id")}: {exc}')
                    continue
                store(key, article['title_ja'], article['summary_ja'], {'article': article, 'model': model})
            selected.append({**event, 'article': article})
        return selected
