"""Patch existing Yapp Outings CSS and search page without wholesale replacement."""
from pathlib import Path
from datetime import datetime
import shutil
import sys

root = Path.cwd()
css_path = root / 'outings/static/outings/css/outings.css'
search_path = root / 'outings/templates/outings/search.html'
source = Path(__file__).resolve().parent / 'outings_ui_polish.css'
marker = '/* Yapp Outings UI polish v1 — narrow, additive overrides */'

for p in (css_path, search_path):
    if not p.is_file():
        sys.exit(f'ERROR: File not found: {p}. Run at project root.')

css = css_path.read_text(encoding='utf-8')
search = search_path.read_text(encoding='utf-8')
if marker in css:
    print('CSS already patched; skipping duplicate.')
else:
    backup = css_path.with_suffix('.before_ui_polish.css.bak')
    shutil.copy2(css_path, backup)
    css_path.write_text(css.rstrip() + '\n\n' + source.read_text(encoding='utf-8'), encoding='utf-8')
    print(f'CSS updated. Backup: {backup}')

old = '<label><input type="checkbox" name="tag" value="family" {% if family_only %}checked{% endif %}> 👶 子連れ</label>'
new = '''<label class="outings-family-choice">
                <input type="checkbox" name="tag" value="family" {% if family_only %}checked{% endif %}>
                <span>👶 子どもと一緒に楽しむ <span class="outings-family-description">（子連れ向けだけを表示）</span></span>
            </label>'''
if old in search:
    backup = search_path.with_suffix('.before_ui_polish.html.bak')
    shutil.copy2(search_path, backup)
    search_path.write_text(search.replace(old, new, 1), encoding='utf-8')
    print(f'Family UI updated. Backup: {backup}')
elif 'class="outings-family-choice"' in search:
    print('Family UI already patched.')
else:
    print('WARNING: Family checkbox HTML differs; kept unchanged. CSS categories/header still updated.')
print('Done. No Git commit or push performed.')
