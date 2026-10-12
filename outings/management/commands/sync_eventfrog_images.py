"""Copy Eventfrog API images to Cloudinary, then update existing Outings events.

Defaults to a read-only dry run. Does not alter user submissions, occurrences,
comments, hearts, titles or approval status. Does not handle cancellations.
"""
import os
from collections import defaultdict
from urllib.parse import urlparse

import requests
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from outings.models import Event, EventfrogOccurrenceLink
from outings.services.eventfrog import collect


def _valid_source_image(url):
    if not isinstance(url, str) or len(url) > 1000:
        return False
    try:
        parts = urlparse(url.strip())
        return (parts.scheme == 'https' and bool(parts.hostname)
                and parts.username is None and parts.password is None)
    except ValueError:
        return False


class Command(BaseCommand):
    help = 'Backfill Eventfrog event images into Cloudinary (dry-run by default).'

    def add_arguments(self, parser):
        parser.add_argument('--commit', action='store_true')
        parser.add_argument('--limit', type=int, default=10, help='Maximum image uploads, 1..200')
        parser.add_argument('--pages', type=int, default=20)
        parser.add_argument('--days', type=int, default=45)
        parser.add_argument('--refresh', action='store_true', help='Re-upload existing Cloudinary photos')

    def handle(self, *args, **opts):
        if not 1 <= opts['limit'] <= 200:
            raise CommandError('--limit must be between 1 and 200')
        if not 1 <= opts['pages'] <= 60 or not 1 <= opts['days'] <= 90:
            raise CommandError('--pages 1..60 and --days 1..90 required')

        # Check credentials before fetching events to avoid a costly no-op.
        if opts['commit']:
            cloud = os.getenv('CLOUDINARY_CLOUD_NAME', '').strip()
            key = os.getenv('CLOUDINARY_API_KEY', '').strip()
            secret = os.getenv('CLOUDINARY_API_SECRET', '').strip()
            if not all((cloud, key, secret)):
                raise CommandError('Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET first')
            if not cloud.replace('-', '').replace('_', '').isalnum():
                raise CommandError('Invalid CLOUDINARY_CLOUD_NAME')

        # One API snapshot; images are selected only for events already linked
        # in the database. Absence from the snapshot is not cancellation.
        rows = collect(pages=opts['pages'], days=opts['days'])
        source_by_id = {
            str(row['id']): row
            for row in rows
            if row.get('id') and _valid_source_image(row.get('image_url'))
        }
        links = (
            EventfrogOccurrenceLink.objects
            .filter(eventfrog_id__in=list(source_by_id))
            .values_list('eventfrog_id', 'event_id')
        )
        options_by_event = defaultdict(list)
        for external_id, event_id in links.iterator(chunk_size=1000):
            options_by_event[event_id].append(source_by_id[external_id])

        # Also match source/external_id in case some occurrence links are absent.
        published = list(
            Event.objects.filter(source__name__iexact='Eventfrog', status=Event.Status.PUBLISHED)
            .only('id', 'external_id', 'image_url', 'title')
        )
        selected = []
        for event in published:
            sources = options_by_event.get(event.pk, [])
            own = source_by_id.get(str(event.external_id))
            if own:
                sources = [own] + sources
            if not sources:
                continue
            # Avoid re-uploading once a persisted Cloudinary photo exists.
            if (not opts['refresh'] and 'res.cloudinary.com/' in (event.image_url or '')):
                continue
            candidate = next((r for r in sources if _valid_source_image(r.get('image_url'))), None)
            if candidate:
                selected.append((event, candidate))

        # Sort by tier where the model includes it; this gives featured priority.
        if published and hasattr(published[0], 'listing_tier'):
            # Our .only() queryset intentionally excludes tier; explicitly fetch priorities.
            priorities = dict(Event.objects.filter(pk__in=[e.pk for e, _ in selected]).values_list('pk', 'listing_tier'))
            selected.sort(key=lambda item: ({'featured': 0, 'standard': 1, 'compact': 2}.get(priorities.get(item[0].pk), 3), item[0].pk))
        else:
            selected.sort(key=lambda item: item[0].pk)

        total = len(selected)
        selected = selected[:opts['limit']]
        self.stdout.write(f'Eligible existing published Eventfrog events with an image: {total}; batch={len(selected)}')
        for event, source in selected[:10]:
            self.stdout.write(f'  Event #{event.pk}: {event.title[:60]} (source event {source["id"]})')
        if not opts['commit']:
            self.stdout.write('DRY RUN: no uploads, no DB writes. Use --commit after checking the preview.')
            return

        upload_url = f'https://api.cloudinary.com/v1_1/{cloud}/image/upload'
        stats = {'uploaded': 0, 'failed': 0, 'unchanged': 0}
        with requests.Session() as session:
            session.auth = (key, secret)
            for event, source in selected:
                # Stable public ID ensures re-runs cannot multiply image files.
                public_id = f'yapp/outings/eventfrog/event-{event.pk}'
                try:
                    response = session.post(
                        upload_url,
                        data={
                            'file': source['image_url'],
                            'public_id': public_id,
                            'overwrite': 'true' if opts['refresh'] else 'false',
                            'resource_type': 'image',
                            'tags': 'yapp_outings,eventfrog',
                        },
                        timeout=90,
                    )
                    response.raise_for_status()
                    uploaded = response.json()
                    url = uploaded.get('secure_url', '')
                    if not isinstance(url, str) or not url.startswith(f'https://res.cloudinary.com/{cloud}/'):
                        raise ValueError('Cloudinary did not return an expected secure_url')
                    with transaction.atomic():
                        updated = Event.objects.filter(
                            pk=event.pk,
                            source__name__iexact='Eventfrog',
                            status=Event.Status.PUBLISHED,
                        ).update(image_url=url)
                    if updated:
                        stats['uploaded'] += 1
                        self.stdout.write(self.style.SUCCESS(f'Image saved for Event #{event.pk}'))
                    else:
                        stats['unchanged'] += 1
                except (requests.RequestException, ValueError) as exc:
                    stats['failed'] += 1
                    self.stderr.write(f'Image failed for Event #{event.pk}: {type(exc).__name__}: {str(exc)[:180]}')
        self.stdout.write(f'Finished: {stats}')
