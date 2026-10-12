"""Cloudinary uploads for freshly imported daily Eventfrog events.

Uses the SAME API snapshot already obtained by daily_outings. Never touches
member posts or already-persisted Cloudinary images. No physical deletes.
"""
import os
from collections import defaultdict
from urllib.parse import urlparse

import requests
from django.db import transaction
from outings.models import Event, EventfrogOccurrenceLink


def _valid_url(url):
    if not isinstance(url, str) or len(url) > 1000:
        return False
    try:
        p = urlparse(url.strip())
        return p.scheme == 'https' and bool(p.hostname) and not p.username and not p.password
    except ValueError:
        return False


def upload_images_for_selected(selected, raw, *, max_uploads=15):
    """Return counts; individual failed uploads are logged and do not halt the batch.

    Eventfrog's own image rights/attribution requirements must be satisfied
    separately. Do not enable --images until approved for production.
    """
    cloud = os.environ['CLOUDINARY_CLOUD_NAME'].strip()
    key = os.environ['CLOUDINARY_API_KEY'].strip()
    secret = os.environ['CLOUDINARY_API_SECRET'].strip()
    if not cloud.replace('-', '').replace('_', '').isalnum():
        raise ValueError('Invalid Cloudinary cloud name')

    candidate_ids = {str(o.get('id')) for e in selected for o in e.get('occurrences', []) if o.get('id')}
    candidate_ids.update(str(e.get('id')) for e in selected if e.get('id'))
    raw_by_id = {str(e['id']): e for e in raw if str(e.get('id')) in candidate_ids and _valid_url(e.get('image_url'))}
    linked_rows = EventfrogOccurrenceLink.objects.filter(eventfrog_id__in=candidate_ids).values_list('eventfrog_id', 'event_id')
    by_event = defaultdict(list)
    for external_id, event_id in linked_rows:
        if external_id in raw_by_id:
            by_event[event_id].append(raw_by_id[external_id]['image_url'])

    events = Event.objects.filter(source__name__iexact='Eventfrog', status=Event.Status.PUBLISHED,
                                  pk__in=list(by_event)).only('pk', 'image_url', 'external_id')
    stats = {'uploaded': 0, 'failed': 0, 'already_saved': 0, 'no_image': 0}
    upload_url = f'https://api.cloudinary.com/v1_1/{cloud}/image/upload'
    with requests.Session() as session:
        session.auth = (key, secret)
        for event in events:
            if sum((stats['uploaded'], stats['failed'])) >= max_uploads:
                break
            if 'res.cloudinary.com/' in (event.image_url or ''):
                stats['already_saved'] += 1
                continue
            choices = by_event.get(event.pk) or []
            own = raw_by_id.get(str(event.external_id))
            if own and own.get('image_url'):
                choices.insert(0, own['image_url'])
            if not choices:
                stats['no_image'] += 1
                continue
            try:
                response = session.post(upload_url, data={
                    'file': choices[0], 'public_id': f'yapp/outings/eventfrog/event-{event.pk}',
                    'overwrite': 'false', 'resource_type': 'image', 'tags': 'yapp_outings,eventfrog',
                }, timeout=90)
                response.raise_for_status()
                value = response.json().get('secure_url')
                if not isinstance(value, str) or not value.startswith(f'https://res.cloudinary.com/{cloud}/'):
                    raise ValueError('Cloudinary returned invalid secure_url')
                with transaction.atomic():
                    updated = Event.objects.filter(pk=event.pk, source__name__iexact='Eventfrog',
                                                   status=Event.Status.PUBLISHED).update(image_url=value)
                if updated:
                    stats['uploaded'] += 1
                    print(f'[Cloudinary] Event #{event.pk}: saved', flush=True)
            except (requests.RequestException, ValueError) as exc:
                stats['failed'] += 1
                print(f'[Cloudinary] Event #{event.pk}: FAILED {type(exc).__name__}: {str(exc)[:160]}', flush=True)
    return stats
