"""Rewrite the Japanese text of already-published Eventfrog events with the current AI prompt.

Use once after a prompt change, so older listings lose their "不明 / 〜ではない"
caveats and get highlights and price fields. Dry run unless --commit.

    python manage.py rewrite_outings_articles            # count only
    python manage.py rewrite_outings_articles --commit   # about 1 AI call per event
"""
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from outings.models import Event, EventCategory, EventTag
from outings.services import ai_editor
from outings.services.importer import CATEGORY_NAMES, TAG_NAMES


def event_material(event, now):
    occurrences = [
        {'start': o.start_at.isoformat(), 'end': o.end_at.isoformat() if o.end_at else None}
        for o in event.occurrences.all() if not o.is_cancelled
    ]
    return {
        'title': event.title_original or event.title,
        'description': event.description_original or event.summary_ja,
        'venue': event.location.name if event.location else '',
        'city': event.location.city if event.location else '',
        'organizer': '',
        'occurrences': occurrences,
    }


class Command(BaseCommand):
    help = 'Rewrite AI text of published, upcoming Eventfrog events. DRY RUN unless --commit.'

    def add_arguments(self, parser):
        parser.add_argument('--commit', action='store_true')
        parser.add_argument('--limit', type=int, default=300)

    def handle(self, *args, **opts):
        if not 1 <= opts['limit'] <= 1000:
            raise CommandError('--limit must be between 1 and 1000')
        now = timezone.now()
        events = [
            e for e in (
                Event.objects.filter(source__name__iexact='Eventfrog', status=Event.Status.PUBLISHED)
                .filter(Q(occurrences__end_at__gt=now) | Q(occurrences__end_at__isnull=True, occurrences__start_at__gte=now))
                .distinct().select_related('location').prefetch_related('occurrences')
            )
            if (e.ai_details or {}).get('version') != ai_editor.ARTICLE_VERSION
        ][:opts['limit']]
        self.stdout.write(f'Events to rewrite: {len(events)}')
        if not opts['commit']:
            self.stdout.write('DRY RUN: no AI calls, no DB changes.')
            return
        done = failed = 0
        for event in events:
            try:
                article = ai_editor.write_article(event_material(event, now), now=now)
            except ai_editor.AIError as exc:
                failed += 1
                self.stderr.write(f'#{event.pk}: {exc}')
                continue
            slug = article['category'] if article['category'] in CATEGORY_NAMES else 'other'
            event.category, _ = EventCategory.objects.get_or_create(slug=slug, defaults={'name': CATEGORY_NAMES[slug]})
            event.title = article['title_ja'][:250]
            event.summary_ja = article['summary_ja']
            event.highlight_ja = article['highlight_ja'][:120]
            event.language_barrier = article['language_barrier']
            event.is_free = article['is_free'] is True
            event.price_text = article['price_text']
            event.is_indoor = article['setting'] in ('indoor', 'both')
            event.is_outdoor = article['setting'] in ('outdoor', 'both')
            details = dict(event.ai_details or {})
            details.update(
                age_note=article['age_note'], booking=article['booking'],
                price_known=article['is_free'] is not None or bool(article['price_text']),
                version=article['version'],
            )
            event.ai_details = details
            event.ai_processed_at = now
            event.save()
            event.tags.set([
                EventTag.objects.get_or_create(slug=t, defaults={'name': TAG_NAMES[t]})[0]
                for t in article['tags'] if t in TAG_NAMES
            ])
            done += 1
            self.stdout.write(f'#{event.pk}: {event.title}')
        self.stdout.write(self.style.SUCCESS(f'Rewritten: {done}, failed: {failed}'))
