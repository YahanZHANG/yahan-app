"""Remove events that are over.

- Ended Eventfrog events are unpublished right away (as before).
- Every event whose last date ended more than DELETE_AFTER ago is deleted
  from the DB, with its dates, hearts and comments. Its Cloudinary photo is
  deleted too (best effort; a failure is only logged).
"""
from datetime import timedelta
from urllib.parse import urlparse

import requests
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from django.db.models import Max, Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from outings.models import Event
from outings.services.user_event_cloudinary import get_cloudinary_settings


DELETE_AFTER = timedelta(days=1)


def ended_events():
    """Events with dates, annotated with when their last date ends."""
    active = Q(occurrences__is_cancelled=False)
    return Event.objects.annotate(
        last_end=Max(Coalesce('occurrences__end_at', 'occurrences__start_at'), filter=active),
        last_any=Max(Coalesce('occurrences__end_at', 'occurrences__start_at')),
    ).annotate(
        finished=Coalesce('last_end', 'last_any'),
    ).filter(finished__isnull=False)


def cloudinary_public_id(url, cloud):
    """'https://res.cloudinary.com/<cloud>/image/upload/v1/a/b.jpg' -> 'a/b'."""
    parts = urlparse(url or '').path.strip('/').split('/')
    if urlparse(url or '').hostname != 'res.cloudinary.com' or parts[:3] != [cloud, 'image', 'upload']:
        return None
    rest = parts[3:]
    if rest and rest[0][:1] == 'v' and rest[0][1:].isdigit():
        rest = rest[1:]
    if not rest:
        return None
    rest[-1] = rest[-1].rsplit('.', 1)[0]
    return '/'.join(rest)


def delete_photos(urls, write):
    try:
        cloud, key, secret = get_cloudinary_settings()
    except ValidationError:
        return 0
    ids = sorted({pid for pid in (cloudinary_public_id(u, cloud) for u in urls) if pid})
    deleted = 0
    for start in range(0, len(ids), 100):
        try:
            response = requests.delete(
                f'https://api.cloudinary.com/v1_1/{cloud}/resources/image/upload',
                params=[('public_ids[]', pid) for pid in ids[start:start + 100]],
                auth=(key, secret), timeout=60,
            )
            response.raise_for_status()
            deleted += sum(1 for v in response.json().get('deleted', {}).values() if v == 'deleted')
        except (requests.RequestException, ValueError) as exc:
            write(f'Cloudinary delete failed: {type(exc).__name__}: {str(exc)[:160]}')
    return deleted


class Command(BaseCommand):
    help = 'Unpublish ended Eventfrog events and delete events that ended over a day ago. Dry run unless --commit.'

    def add_arguments(self, parser):
        parser.add_argument('--commit', action='store_true')

    def handle(self, *args, **options):
        now = timezone.now()
        to_unpublish = ended_events().filter(
            source__name__iexact='Eventfrog', status=Event.Status.PUBLISHED, finished__lt=now,
        )
        to_delete = ended_events().filter(finished__lt=now - DELETE_AFTER)
        delete_ids = list(to_delete.values_list('pk', flat=True))
        self.stdout.write(f'Ended Eventfrog events: {to_unpublish.count()}; events to delete: {len(delete_ids)}')
        if not options['commit']:
            self.stdout.write('DRY RUN: DB unchanged')
            return

        unpublished = Event.objects.filter(
            pk__in=list(to_unpublish.values_list('pk', flat=True))
        ).update(status=Event.Status.CANCELLED)
        photos = list(Event.objects.filter(pk__in=delete_ids).exclude(image_url='').values_list('image_url', flat=True))
        deleted, _ = Event.objects.filter(pk__in=delete_ids).delete()
        removed_photos = delete_photos(photos, self.stderr.write) if photos else 0
        self.stdout.write(self.style.SUCCESS(
            f'Unpublished: {unpublished}; deleted events: {len(delete_ids)} ({deleted} rows); '
            f'Cloudinary photos deleted: {removed_photos}'
        ))
