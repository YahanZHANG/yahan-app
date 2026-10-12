"""Unpublish expired Eventfrog events while keeping comments/hearts and user submissions."""
from django.core.management.base import BaseCommand
from django.db.models import Max, Q
from django.utils import timezone
from outings.models import Event


class Command(BaseCommand):
    help = 'Unpublish ended Eventfrog events. Dry run unless --commit.'

    def add_arguments(self, parser):
        parser.add_argument('--commit', action='store_true')

    def handle(self, *args, **options):
        now = timezone.now()
        records = (Event.objects.filter(
            source__name__iexact='Eventfrog', status=Event.Status.PUBLISHED
        ).annotate(
            last_end=Max('occurrences__end_at', filter=Q(occurrences__is_cancelled=False)),
            last_start=Max('occurrences__start_at', filter=Q(occurrences__is_cancelled=False)),
        ))
        expired = [e.pk for e in records if e.last_end is not None and e.last_start is not None and e.last_end < now]
        self.stdout.write(f'Ended Eventfrog events: {len(expired)}')
        if not options['commit']:
            self.stdout.write('DRY RUN: DB unchanged')
            return
        count = Event.objects.filter(pk__in=expired, source__name__iexact='Eventfrog', status=Event.Status.PUBLISHED).update(status=Event.Status.CANCELLED)
        self.stdout.write(self.style.SUCCESS(f'Unpublished: {count}; no records deleted'))
