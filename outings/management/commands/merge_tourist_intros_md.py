"""Merge a batch of introductions written as Markdown into tourist_intros.json.

The Markdown lists spots as "12. <MySwitzerland title>", then a line like
"散策・ハイキング｜ベルン州", then the introduction; source lines such as
"Schweiz Tourismus+1" or favicon links are dropped, and so is anything
after "以上で…". A later "26. <title>（…確定版）" entry
replaces the earlier one.

    python manage.py merge_tourist_intros_md batch.md
"""

import json
import re

from django.core.management.base import BaseCommand

from .apply_family_intros import FAMILY_DATA
from .apply_tourist_intros import DATA

HEADER = re.compile(r"^(\d+)\. (.+?)(（[^）]*確定版）)?\s*$")
SECTION = re.compile(r"^\d+〜\d+件|^第\d+弾|^ーー|^以上で|^ここから|^これで")
JAPANESE = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")


def is_source(line):
    """Reference lines: link/favicon markdown, or a short line with no Japanese (SchweizMobil, Führung+1)."""
    return bool(re.search(r"\]\(https?://", line)) or (len(line) < 60 and not JAPANESE.search(line))


def parse(text):
    entries, current = {}, None
    for line in text.splitlines():
        heading = re.match(r"^#{1,2}\s", line)  # "# …" / "## …" = a section, not a spot
        line = re.sub(r"^#+\s*", "", line.rstrip())  # Markdown headings
        line = re.sub(r"^\*\*(.+)\*\*$", r"\1", line)  # **bold** lines
        match = HEADER.match(line)
        if match:
            current = {"title": match.group(2).strip(), "lines": []}
            entries[int(match.group(1))] = current
            continue
        if current is None:
            continue
        if heading or SECTION.match(line):
            current = None
            continue
        if line.strip():
            current["lines"].append(line.strip())
    result = {}
    for number in sorted(entries):
        lines = entries[number]["lines"]
        if lines and "｜" in lines[0] and len(lines[0]) < 60:
            lines = lines[1:]  # category｜region
        body = "\n".join(line for line in lines if not is_source(line))
        if body:
            result[entries[number]["title"]] = body
    return result


class Command(BaseCommand):
    help = "Merge Markdown introductions into outings/data/tourist_intros.json."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--family", action="store_true", help="子連れスポット (family_intros.json, keyed by name)")

    def handle(self, *args, **options):
        new = parse(open(options["path"], encoding="utf-8").read())
        data = DATA
        if options["family"]:
            data = FAMILY_DATA
            new = {re.sub(r"（[^）]*）$", "", title).strip(): text for title, text in new.items()}  # drop the Japanese name
        current = json.loads(data.read_text(encoding="utf-8")) if data.exists() else {}
        added = sum(1 for title in new if title not in current)
        current.update(new)
        data.write_text(json.dumps(current, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        self.stdout.write(f"{len(new)} introductions read ({added} new); {len(current)} in the file.")
