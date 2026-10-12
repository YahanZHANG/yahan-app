"""Fetch current Eventfrog snapshot and update known occurrence times (dry run default)."""
from django.core.management.base import BaseCommand, CommandError
from outings.services.eventfrog import collect
from outings.services.eventfrog_existing_sync import sync_existing


class Command(BaseCommand):
    help = 'Update known Eventfrog occurrence dates. Dry run by default.'

    def add_arguments(self, parser):
        parser.add_argument('--commit', action='store_true')
        parser.add_argument('--pages', type=int, default=20)
        parser.add_argument('--days', type=int, default=45)

    def handle(self, *args, **options):
        if not (1 <= options['pages'] <= 60 and 1 <= options['days'] <= 90):
            raise CommandError('pages=1..60; days=1..90')
        events = collect(pages=options['pages'], days=options['days'])
        result = sync_existing(events, commit=options['commit'])
        self.stdout.write(f"Existing Eventfrog sync ({'COMMIT' if options['commit'] else 'DRY RUN'}): {result}")
        self.stdout.write('Missing API IDs are NOT treated as cancelled; member posts unchanged.')
