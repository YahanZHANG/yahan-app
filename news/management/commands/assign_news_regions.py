from django.core.management.base import BaseCommand

from news.models import (
    Article,
    Region,
)

from news.region_classifier import (
    classify_region_slugs,
)


class Command(BaseCommand):

    help = (
        "既存のニュース記事へ"
        "地域タグを自動付与します。"
    )

    def add_arguments(
        self,
        parser,
    ):

        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="処理する記事数",
        )

        parser.add_argument(
            "--force",
            action="store_true",
            help=(
                "既に地域タグがある記事も"
                "再分類する"
            ),
        )

    def handle(
        self,
        *args,
        **options,
    ):

        limit = options[
            "limit"
        ]

        force = options[
            "force"
        ]

        articles = (
            Article.objects
            .all()
            .order_by(
                "-published_at"
            )
        )

        if not force:

            articles = (
                articles.filter(
                    regions__isnull=True
                )
                .distinct()
            )

        if limit:

            articles = (
                articles[:limit]
            )

        region_map = {
            region.slug: region
            for region in (
                Region.objects
                .filter(
                    is_active=True
                )
            )
        }

        processed = 0
        missing = 0

        for article in articles:

            region_slugs = (
                classify_region_slugs(
                    article
                )
            )

            regions = []

            for slug in region_slugs:

                region = (
                    region_map.get(
                        slug
                    )
                )

                if region:

                    regions.append(
                        region
                    )

                else:

                    self.stdout.write(
                        self.style.WARNING(
                            f"Region not found: "
                            f"{slug}"
                        )
                    )

                    missing += 1

            article.regions.set(
                regions
            )

            processed += 1

            self.stdout.write(
                f"[{article.pk}] "
                f"{article.title_ja or article.title_original}"
                f" -> "
                f"{', '.join(region_slugs)}"
            )

        self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS(
                f"Processed: {processed}"
            )
        )

        if missing:

            self.stdout.write(
                self.style.WARNING(
                    f"Missing Region records: "
                    f"{missing}"
                )
            )