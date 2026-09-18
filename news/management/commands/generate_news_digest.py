from django.core.management.base import BaseCommand

from news.services.digest_generator import (
    generate_news_digest,
)


class Command(BaseCommand):

    help = (
        "Generate the latest Yahan News digest."
    )


    def add_arguments(
        self,
        parser,
    ):

        parser.add_argument(
            "--period",
            choices=[
                "morning",
                "late_morning",
                "afternoon",
                "evening",
            ],
            default=None,
        )


    def handle(
        self,
        *args,
        **options,
    ):

        digest = generate_news_digest(
            period=options["period"]
        )


        if not digest:

            self.stdout.write(
                self.style.WARNING(
                    "No new articles for digest."
                )
            )

            return


        self.stdout.write(
            self.style.SUCCESS(
                (
                    "Digest generated. "
                    f"Articles: "
                    f"{digest.article_count}"
                )
            )
        )


        self.stdout.write("")
        self.stdout.write(
            digest.summary_ja
        )