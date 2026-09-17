from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from news.models import Article


class Command(BaseCommand):
    help = (
        "Delete news articles older than 7 days "
        "unless they are favorited."
    )


    def handle(self, *args, **options):

        cutoff = (
            timezone.now()
            - timedelta(days=7)
        )

        old_articles = (
            Article.objects
            .filter(
                published_at__lt=cutoff
            )
            .filter(
                favorites__isnull=True
            )
            .distinct()
        )

        count = old_articles.count()

        old_articles.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {count} old articles."
            )
        )