Yapp Outings UI polish v1

1. Put the ZIP at the root of your yahan-app project.
2. Expand-Archive -Path ".\yapp_outings_ui_polish_v1.zip" -DestinationPath "." -Force
3. python .\outings_ui_update\apply_outings_ui.py
4. python manage.py check
5. Ctrl+F5 on /outings/search/ and /outings/

No DB changes, migrations, AI calls, image calls, Git commits, or pushes.
The script backs up existing CSS and search template as *.bak.
Category: existing radio inputs styled as compact chips.
Family: preserves tag=family GET semantics.
Desktop sticky header approx 70px tall; change --outings-desktop-header-height if overlap.
