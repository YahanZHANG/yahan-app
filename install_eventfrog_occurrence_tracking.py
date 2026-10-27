"""Install only the Eventfrog ID tracking model. Re-runnable safely."""
from pathlib import Path
import shutil

path = Path('outings/models.py')
if not path.is_file():
    raise SystemExit('Run from the yahan-app project root')
s = path.read_text(encoding='utf-8')
if 'class EventfrogOccurrenceLink(' in s:
    raise SystemExit('EventfrogOccurrenceLink already exists; nothing changed')
if 'class EventOccurrence(' not in s or 'class EventfrogTranslationCache(' not in s:
    raise SystemExit('Unexpected models.py: expected EventOccurrence and DB translation cache. No change made.')
model = '''\n\nclass EventfrogOccurrenceLink(models.Model):\n    """Exact Eventfrog event ID to local occurrence relationship."""\n    eventfrog_id = models.CharField(max_length=100, unique=True)\n    event = models.ForeignKey(\n        "Event", on_delete=models.CASCADE, related_name="eventfrog_links"\n    )\n    occurrence = models.ForeignKey(\n        "EventOccurrence", on_delete=models.CASCADE, related_name="eventfrog_links"\n    )\n    last_source_start_at = models.DateTimeField(null=True, blank=True)\n    last_seen_at = models.DateTimeField(auto_now=True)\n\n    def __str__(self):\n        return self.eventfrog_id\n'''
backup = path.with_suffix('.py.before_eventfrog_tracking.bak')
shutil.copy2(path, backup)
path.write_text(s + model, encoding='utf-8')
print('Added EventfrogOccurrenceLink model in outings/models.py')
print('Backup:', backup)
