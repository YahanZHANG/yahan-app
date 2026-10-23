"""
スイスで代わりになる食材 (代用品として登録された食材) のうち、写真がないものを
Wikimedia Commons で探して付ける。一度探した食材は二度と探さないので、
デプロイのたびに動かしても、外した写真がまた付くことはない。
"""

import time

from django.core.management.base import BaseCommand

from washoku.models import Ingredient
from washoku.photos import commons_query, find_commons_photo


class Command(BaseCommand):
    help = "代わりの食材の写真を Wikimedia Commons で探して付ける (一度探した食材はとばす)"

    def handle(self, *args, **options):

        targets = Ingredient.objects.filter(
            substitutes_for__isnull=False,
            photo_url="",
            photo_auto_tried=False,
        ).distinct()

        found = 0

        for ingredient in targets:

            try:
                photo = find_commons_photo(commons_query(ingredient))
            except Exception as error:  # 通信の失敗は、次の起動でもう一度
                self.stderr.write(f"{ingredient.name}: {type(error).__name__}")
                continue

            if photo:
                ingredient.photo_url = photo["url"]
                ingredient.photo_credit = photo["credit"]
                ingredient.photo_source = photo["source"]
                found += 1

            ingredient.photo_auto_tried = True
            ingredient.save(update_fields=["photo_url", "photo_credit", "photo_source", "photo_auto_tried"])

            # Wikimedia に負担をかけないよう、少し間をあける
            time.sleep(1)

        self.stdout.write(f"写真を付けた食材: {found}件")
