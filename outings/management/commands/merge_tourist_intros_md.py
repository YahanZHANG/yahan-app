"""Merge a batch of introductions written as Markdown into tourist_intros.json.

The Markdown lists spots as "12. <MySwitzerland title>", then a line like
"散策・ハイキング｜ベルン州", then the introduction; source lines such as
"Schweiz Tourismus+1" are dropped. A later "26. <title>（…確定版）" entry
replaces the earlier one.

    python manage.py merge_tourist_intros_md batch.md
"""

import json
import re

from django.core.management.base import BaseCommand

from .apply_tourist_intros import DATA

HEADER = re.compile(r"^(\d+)\. (.+?)(（[^）]*確定版）)?\s*$")
SOURCE = re.compile(r"^(Schweiz Tourismus|Switzerland Tourism|[A-Za-z .]+)(\+\d+)?$")
SECTION = re.compile(r"^\d+〜\d+件|^第\d+弾|^ーー")


def parse(text):
    entries, current = {}, None
    for line in text.splitlines():
        line = line.rstrip()
        match = HEADER.match(line)
        if match:
            current = {"title": match.group(2).strip(), "lines": []}
            entries[int(match.group(1))] = current
            continue
        if current is None:
            continue
        if SECTION.match(line):
            current = None
            continue
        if line.strip():
            current["lines"].append(line.strip())
    result = {}
    for number in sorted(entries):
        lines = entries[number]["lines"]
        if lines and "｜" in lines[0] and len(lines[0]) < 60:
            lines = lines[1:]  # category｜region
        body = "\n".join(line for line in lines if not SOURCE.match(line))
        if body:
            result[entries[number]["title"]] = body
    return result


class Command(BaseCommand):
    help = "Merge Markdown introductions into outings/data/tourist_intros.json."

    def add_arguments(self, parser):
        parser.add_argument("path")

    def handle(self, *args, **options):
        new = parse(open(options["path"], encoding="utf-8").read())
        current = json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else {}
        added = sum(1 for title in new if title not in current)
        current.update(new)
        DATA.write_text(json.dumps(current, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        self.stdout.write(f"{len(new)} introductions read ({added} new); {len(current)} in the file.")
