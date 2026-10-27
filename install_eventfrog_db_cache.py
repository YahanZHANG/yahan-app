"""One-time source patch; run from Django project root; does not touch DB."""
from pathlib import Path
import shutil

models = Path('outings/models.py')
sync = Path('outings/management/commands/sync_eventfrog_outings.py')
if not models.is_file() or not sync.is_file():
    raise SystemExit('Run from yahan-app root: outings/models.py / sync_eventfrog_outings.py required')

m = models.read_text(encoding='utf-8')
s = sync.read_text(encoding='utf-8')
if 'class EventfrogTranslationCache(' in m or 'prepare_translation_csv(' in s:
    raise SystemExit('Already patched (or partially patched). No changes made; inspect the files.')

anchors = [
    'from .eventfrog_quality import evaluate',
    "        self.stdout.write('4/5 Quality filter + JP translation of new PASS rows')",
    "        if not TRANSLATED.is_file():",
]
if not all(a in s for a in anchors):
    raise SystemExit('Unexpected sync_eventfrog_outings.py version; no files were changed.')

new_model = '''

class EventfrogTranslationCache(models.Model):
    """Reusable JP translation keyed by a stable Eventfrog series_key."""
    series_key = models.CharField(max_length=255, unique=True)
    title_ja = models.CharField(max_length=250)
    summary_ja = models.TextField()
    row_data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title_ja
'''

s = s.replace(
    'from .eventfrog_quality import evaluate',
    'from .eventfrog_quality import evaluate\n'
    'from outings.eventfrog_translation_store import (\n'
    '    prepare_translation_csv, persist_translation_csv,\n'
    ')',
    1,
)
s = s.replace(
    "        self.stdout.write('4/5 Quality filter + JP translation of new PASS rows')",
    "        self.stdout.write('4/5 Quality filter + JP translation of new PASS rows')\n"
    "        cached = prepare_translation_csv(TRANSLATED, REVIEW, commit=opts['commit'])\n"
    "        self.stdout.write(f'DB translation cache restored: {cached} series')",
    1,
)
s = s.replace(
    "        if not TRANSLATED.is_file():",
    "        if opts['commit']:\n"
    "            saved = persist_translation_csv(TRANSLATED)\n"
    "            self.stdout.write(f'DB translation cache saved: {saved} series')\n"
    "        if not TRANSLATED.is_file():",
    1,
)

for file in (models, sync):
    shutil.copy2(file, file.with_name(file.name + '.before_db_cache.bak'))
models.write_text(m + new_model, encoding='utf-8')
sync.write_text(s, encoding='utf-8')
print('Updated outings/models.py and sync_eventfrog_outings.py')
print('Backups: *.before_db_cache.bak (do not commit backups)')
print('Next: python manage.py makemigrations outings && python manage.py migrate')
