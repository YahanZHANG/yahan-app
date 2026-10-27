import csv
import hashlib
from pathlib import Path

from outings.models import Event

path = Path("outings_audit/eventfrog_review_queue.csv")

with path.open(encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))

for pk in [45, 46]:
    event = Event.objects.get(pk=pk)

    matches = [
        row
        for row in rows
        if row.get("series_key")
        and (
            "series-"
            + hashlib.sha256(
                row["series_key"].encode("utf-8")
            ).hexdigest()[:32]
        ) == event.external_id
    ]

    print("\n==========================")
    print("EVENT:", pk, event.title)
    print("DB occurrence count:", event.occurrences.count())
    print("CSV matching rows:", len(matches))

    for row in matches:
        starts = [
            x.strip()
            for x in row.get("occurrence_starts", "").split("|")
            if x.strip()
        ]

        print("CSV occurrence count:", len(starts))
        print("CSV dates:", starts[:15])