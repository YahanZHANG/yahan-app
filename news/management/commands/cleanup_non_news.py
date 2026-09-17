from django.core.management.base import BaseCommand

from news.models import Article
from news.services.content_filter import (
    should_skip_article,
)


class Command(BaseCommand):
    help = (
        "Delete ads, newsletters, promotions "
        "and other non-news content."
    )

    def handle(
        self,
        *args,
        **options,
    ):
        articles = (
            Article.objects
            .select_related("source")
            .all()
        )

        deleted = 0

        for article in articles:

            if should_skip_article(
                source_name=article.source.name,
                title=article.title_original,
                summary=article.summary_original,
                url=article.source_url,
            ):

                self.stdout.write(
                    (
                        "Deleting: "
                        f"{article.title_original[:100]}"
                    )
                )

                article.delete()

                deleted += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {deleted} non-news articles."
            )
        )