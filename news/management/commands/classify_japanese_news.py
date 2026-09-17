from django.core.management.base import BaseCommand

from news.models import Article

from news.services.japanese_classifier import (
    assign_japanese_topics,
)


class Command(BaseCommand):
    help = (
        "Classify Japanese news articles "
        "without using the OpenAI API."
    )


    def handle(
        self,
        *args,
        **options,
    ):

        articles = (
            Article.objects
            .filter(
                original_language="ja"
            )
            .select_related(
                "source"
            )
        )


        processed = 0


        for article in articles:

            topics = assign_japanese_topics(
                article
            )

            names = (
                ", ".join(
                    topic.name
                    for topic in topics
                )
                if topics
                else "なし"
            )

            self.stdout.write(
                (
                    f"{article.title_ja[:70]}"
                    f" -> {names}"
                )
            )

            processed += 1


        self.stdout.write(
            self.style.SUCCESS(
                (
                    "Finished. "
                    f"Processed: {processed}"
                )
            )
        )