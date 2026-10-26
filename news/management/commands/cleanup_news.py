from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from news.models import Article, NewsDigest


class Command(BaseCommand):
    help = (
        "Delete news articles older than 7 days "
        "unless they are favorited, and digests "
        "older than 7 days."
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

        old_ids = set(
            old_articles.values_list(
                "id",
                flat=True,
            )
        )

        # まとめ役の記事を消すと、残った同じ出来事の記事が
        # バラバラに表示されてしまう。残る記事の1つを新しいまとめ役にする。
        roots = Article.objects.filter(
            id__in=old_ids,
            duplicates__isnull=False,
        ).distinct()

        for root in roots:

            survivors = list(
                root.duplicates
                .exclude(
                    id__in=old_ids,
                )
                .order_by(
                    "published_at",
                    "id",
                )
            )

            if not survivors:
                continue

            new_root = survivors[0]

            Article.objects.filter(
                pk=new_root.pk,
            ).update(
                duplicate_of=None,
            )

            Article.objects.filter(
                pk__in=[
                    article.pk
                    for article in survivors[1:]
                ],
            ).update(
                duplicate_of=new_root,
            )

        count = len(old_ids)

        Article.objects.filter(
            id__in=old_ids,
        ).delete()

        digest_count, _ = (
            NewsDigest.objects
            .filter(
                digest_date__lt=cutoff.date()
            )
            .delete()
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {count} old articles "
                f"and {digest_count} old digests."
            )
        )