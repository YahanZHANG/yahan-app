from django.core.management.base import BaseCommand

from news.models import NewsSource, Topic


class Command(BaseCommand):
    help = "Create default news topics and sources."


    def handle(self, *args, **options):

        topics = [
            (
                "政治・行政",
                "politics",
                "🏛️",
                10,
            ),
            (
                "経済・ビジネス",
                "economy",
                "💼",
                20,
            ),
            (
                "社会・事件",
                "society",
                "🏙️",
                30,
            ),
            (
                "暮らし・制度",
                "life",
                "🏠",
                40,
            ),
            (
                "科学・テクノロジー",
                "technology",
                "💻",
                50,
            ),
            (
                "医療・健康",
                "health",
                "🏥",
                60,
            ),
            (
                "環境・気候",
                "environment",
                "🌿",
                70,
            ),
            (
                "文化・エンタメ",
                "culture",
                "🎭",
                80,
            ),
            (
                "スポーツ",
                "sports",
                "⚽",
                90,
            ),
        ]

        for (
            name,
            slug,
            icon,
            display_order,
        ) in topics:

            Topic.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "icon": icon,
                    "display_order": display_order,
                    "is_active": True,
                },
            )

        sources = [
            (
                "SWI swissinfo.ch",
                "https://www.swissinfo.ch/jpn/",
                "",
                "ja",
                10,
            ),
            (
                "SRF",
                "https://www.srf.ch/news",
                "https://www.srf.ch/news/bnf/rss/1890",
                "de",
                20,
            ),
            (
                "RSI",
                "https://www.rsi.ch/info/",
                "https://www.rsi.ch/info/svizzera/?f=rss",
                "it",
                30,
            ),
            (
                "Swiss Federal Administration",
                "https://www.admin.ch/de/newnsb",
                "",
                "de",
                40,
            ),
            (
                "20 Minuten",
                "https://www.20min.ch/schweiz",
                "",
                "de",
                50,
            ),
            (
                "Blick",
                "https://www.blick.ch/schweiz/",
                "",
                "de",
                60,
            ),
            (
                "Nau.ch",
                "https://www.nau.ch/news/schweiz",
                "",
                "de",
                70,
            ),
            (
                "Watson",
                "https://www.watson.ch/schweiz/",
                "",
                "de",
                80,
            ),
            (
                "RTS",
                "https://www.rts.ch/info/",
                "",
                "fr",
                90,
            ),
        ]

        for (
            name,
            website_url,
            feed_url,
            language,
            display_order,
        ) in sources:

            NewsSource.objects.update_or_create(
                name=name,
                defaults={
                    "website_url": website_url,
                    "feed_url": feed_url,
                    "language": language,
                    "display_order": display_order,
                    "is_active": True,
                },
            )