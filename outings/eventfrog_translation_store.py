"""Persistent Eventfrog Japanese translation bridge for sync_eventfrog_outings.

The database is authoritative. Local CSV is an optional first-time migration source
and is regenerated for the existing translator/importer on every run.
"""
import csv
from pathlib import Path

from django.db import transaction

from outings.models import EventfrogTranslationCache


def read_rows(path):
    if not Path(path).is_file():
        return [], []
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames or []), list(reader)


def write_rows(path, fields, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def prepare_translation_csv(path, review_path, *, commit=False):
    """Restore CSV from DB; optionally import legacy CSV-only translations.

    During --commit only, previous CSV rows are migrated into DB, if their
    series_key has not already been saved. DB wins on collisions.
    """
    csv_fields, csv_rows = read_rows(path)
    review_fields, _ = read_rows(review_path)
    fields = list(dict.fromkeys(review_fields + csv_fields + [
        'series_key', 'title_ja', 'summary_ja', 'review_status'
    ]))
    if commit:
        with transaction.atomic():
            for row in csv_rows:
                key = (row.get('series_key') or '').strip()
                if not key or not row.get('title_ja') or not row.get('summary_ja'):
                    continue
                EventfrogTranslationCache.objects.get_or_create(
                    series_key=key,
                    defaults={
                        'title_ja': row['title_ja'],
                        'summary_ja': row['summary_ja'],
                        'row_data': row,
                    },
                )
    records = {}
    for item in EventfrogTranslationCache.objects.all().iterator(chunk_size=500):
        records[item.series_key] = {
            **item.row_data,
            'series_key': item.series_key,
            'title_ja': item.title_ja,
            'summary_ja': item.summary_ja,
        }
    # Safe non-persistent dry-run fallbacks to existing local CSV.
    if not commit:
        for row in csv_rows:
            key = (row.get('series_key') or '').strip()
            if key and row.get('title_ja') and row.get('summary_ja'):
                records.setdefault(key, row)
    write_rows(path, fields, list(records.values()))
    return len(records)


def persist_translation_csv(path):
    """Upsert successful translations after the AI command completes.

    Never retranslate based on CSV presence. The database is the durable source.
    """
    _, rows = read_rows(path)
    count = 0
    for row in rows:
        key = (row.get('series_key') or '').strip()
        title = (row.get('title_ja') or '').strip()
        summary = (row.get('summary_ja') or '').strip()
        if not key or not title or not summary:
            continue
        EventfrogTranslationCache.objects.update_or_create(
            series_key=key,
            defaults={
                'title_ja': title,
                'summary_ja': summary,
                'row_data': row,
            },
        )
        count += 1
    return count
