"""New Yapp Outings editorial pipeline, read-only DB; old commands not required.

Dry-run: python manage.py sync_outings --offline-json example.json
AI test: python manage.py sync_outings --offline-json example.json --ai --evaluate 20
Live scan: python manage.py sync_outings --pages 3
"""
import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from outings.services.eventfrog import collect, enrich_locations, group
from outings.services.ai_editor import evaluate, editorial_key
from outings.services.selector import select

OUTPUT = Path('outings_ai_data')


class Command(BaseCommand):
    help = 'Curate Eventfrog events with optional AI. No Django DB writes or publication.'

    def add_arguments(self, parser):
        parser.add_argument('--offline-json', help='Eventfrog raw JSON array or {events:[...]}')
        parser.add_argument('--reuse-events', action='store_true', help='Reuse normalized events from last successful event scan; bypass 20-page fetch')
        parser.add_argument('--pages', type=int, default=40)
        parser.add_argument('--per-page', type=int, default=1000)
        parser.add_argument('--days', type=int, default=45)
        parser.add_argument('--target', type=int, default=100)
        parser.add_argument('--evaluate', type=int, default=300, help='Maximum *new* AI calls in this run')
        parser.add_argument('--ai', action='store_true', help='Paid OpenAI API evaluation')
        parser.add_argument('--reselect-only', action='store_true', help='Rebuild selected.json from saved evaluated.json; no Eventfrog/OpenAI calls')
        parser.add_argument('--model', default='gpt-4.1-mini')

    def handle(self, *args, **opts):
        if not 1 <= opts['pages'] <= 60 or not 1 <= opts['per_page'] <= 1000:
            raise CommandError('pages 1..60 and per-page 1..1000 required')
        if not 1 <= opts['days'] <= 90 or not 1 <= opts['target'] <= 500 or not 1 <= opts['evaluate'] <= 2000:
            raise CommandError('days 1..90; target 1..500; evaluate 1..2000 required')
        OUTPUT.mkdir(parents=True, exist_ok=True)
        if opts['reselect_only']:
            if opts['ai'] or opts['reuse_events'] or opts['offline_json']:
                raise CommandError('--reselect-only must be used alone (optionally --target and --days)')
            prior = OUTPUT / 'evaluated.json'
            if not prior.is_file():
                raise CommandError('No outings_ai_data/evaluated.json to reselect')
            evaluated = json.loads(prior.read_text(encoding='utf-8'))
            if not isinstance(evaluated, list):
                raise CommandError('Invalid evaluated.json: expected a list')
            from django.utils import timezone
            selection = select(evaluated, target=opts['target'], now=timezone.now(), days=opts['days'])
            (OUTPUT / 'selected.json').write_text(json.dumps(selection, ensure_ascii=False, indent=2), encoding='utf-8')
            from collections import Counter
            self.stdout.write(self.style.SUCCESS(f'Reselected from {len(evaluated)} saved AI assessments; selected={len(selection)}; paid requests=0'))
            self.stdout.write(f'Listing tiers: {dict(Counter(x["listing_tier"] for x in selection))}; long-running={sum(x["is_long_running"] for x in selection)}')
            self.stdout.write('DB unchanged; no events published.')
            return
        offline = bool(opts['offline_json'])
        raw = None
        if offline:
            p = Path(opts['offline_json'])
            if not p.is_file():
                raise CommandError(f'Missing offline file: {p}')
            raw = json.loads(p.read_text(encoding='utf-8-sig'))
            if isinstance(raw, dict):
                raw = raw.get('events')
            if not isinstance(raw, list):
                raise CommandError('Offline JSON must be a list or {events:[...]}')
        try:
            normalized_path = OUTPUT / 'normalized_events.json'
            if opts['reuse_events']:
                if offline:
                    raise CommandError('--reuse-events cannot be combined with --offline-json')
                if not normalized_path.is_file():
                    raise CommandError('No saved normalized events. Run once without --reuse-events.')
                from datetime import datetime, timedelta
                from django.utils import timezone
                if datetime.fromtimestamp(normalized_path.stat().st_mtime, tz=timezone.get_current_timezone()) < timezone.now() - timedelta(hours=24):
                    raise CommandError('Saved event snapshot older than 24 hours; do a fresh scan')
                candidates = json.loads(normalized_path.read_text(encoding='utf-8'))
                self.stdout.write(f'[Eventfrog] Reusing {len(candidates)} normalized events from disk')
            else:
                candidates = collect(pages=opts['pages'], per_page=opts['per_page'], days=opts['days'], raw_events=raw)
                normalized_path.write_text(json.dumps(candidates, ensure_ascii=False), encoding='utf-8')
                self.stdout.write(f'[Eventfrog] Saved {len(candidates)} normalized events for retry')
            located = enrich_locations(candidates, offline=offline, cache_file=OUTPUT/'locations.json')
        except Exception as exc:
            raise CommandError(f'Eventfrog collection failed: {exc}') from exc
        grouped = group(located)
        self.stdout.write(f'Raw valid events={len(candidates)}; in-region located={len(located)}; series={len(grouped)}')
        (OUTPUT/'candidates.json').write_text(json.dumps(grouped, ensure_ascii=False, indent=2), encoding='utf-8')
        if not opts['ai']:
            self.stdout.write('NO AI/DB changes. Candidate snapshot: outings_ai_data/candidates.json')
            if offline and not located:
                self.stdout.write('Offline location lookup requires outings_ai_data/locations.json from a prior live scan.')
            return
        cache_path = OUTPUT/'ai_cache.json'
        cache = json.loads(cache_path.read_text(encoding='utf-8')) if cache_path.exists() else {}
        if not isinstance(cache, dict):
            raise CommandError('Invalid AI cache format')
        # Take candidates across time, not just first few days.
        from django.utils import timezone
        now = timezone.now()
        buckets = [[], [], [], []]
        for event in grouped:
            from datetime import datetime
            delta = (datetime.fromisoformat(event['start']) - now).total_seconds()/86400
            bucket = 0 if delta <= 7 else 1 if delta <= 14 else 2 if delta <= 30 else 3
            buckets[bucket].append(event)
        ordered = []
        while any(buckets):
            for bucket in buckets:
                if bucket:
                    ordered.append(bucket.pop(0))
        evaluated = []
        new_calls = 0
        for event in ordered:
            cache_key = editorial_key(event, opts['model'])
            data = cache.get(cache_key)
            if data is None:
                if new_calls >= opts['evaluate']:
                    continue
                try:
                    data = evaluate(event, model=opts['model'])
                except Exception as exc:
                    self.stderr.write(f'AI stopped after {new_calls} new evaluations: {exc}')
                    break
                cache[cache_key] = data
                # Save each paid result immediately; safe to restart.
                cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding='utf-8')
                new_calls += 1
            evaluated.append({**event, 'ai': data})
        selection = select(evaluated, target=opts['target'], now=now, days=opts['days'])
        (OUTPUT/'evaluated.json').write_text(json.dumps(evaluated, ensure_ascii=False, indent=2), encoding='utf-8')
        (OUTPUT/'selected.json').write_text(json.dumps(selection, ensure_ascii=False, indent=2), encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'AI evaluated={len(evaluated)}, new paid requests={new_calls}, selected={len(selection)}'))
        from collections import Counter
        self.stdout.write(f'Listing tiers: {dict(Counter(x["listing_tier"] for x in selection))}; long-running={sum(x["is_long_running"] for x in selection)}')
        self.stdout.write('Saved outings_ai_data/selected.json; DB unchanged; no events published.')
