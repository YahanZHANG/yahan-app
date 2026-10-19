"""Import curated Eventfrog events (selected.json) as published; dry-run by default."""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from outings.services.importer import InvalidRow, import_items, validate


class Command(BaseCommand):
    help = 'Import selected.json as published Eventfrog events. DRY RUN unless --commit.'

    def add_arguments(self, parser):
        parser.add_argument('--file', default='outings_ai_data/selected.json')
        parser.add_argument('--commit', action='store_true', help='Create/update and publish Eventfrog events in this database')

    def handle(self, *args, **opts):
        path = Path(opts['file'])
        if not path.is_file():
            raise CommandError(f'No selected JSON: {path}')
        try:
            items = json.loads(path.read_text(encoding='utf-8-sig'))
        except (ValueError, UnicodeError) as exc:
            raise CommandError(f'Invalid JSON: {exc}')
        if not isinstance(items, list):
            raise CommandError('Expected a JSON list')
        if not opts['commit']:
            invalid = 0
            for index, item in enumerate(items, 1):
                try:
                    validate(item)
                except InvalidRow as exc:
                    invalid += 1
                    self.stderr.write(f'Row {index}: {exc}')
            self.stdout.write(f'Validated: {len(items) - invalid} valid, {invalid} invalid. DRY RUN: no DB changes.')
            return
        import_items(items, log=self.stdout.write, warn=self.stderr.write)
