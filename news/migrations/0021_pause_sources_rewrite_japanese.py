from django.db import migrations


# 許可が取れるまで取得しない媒体（2026-11 利用規約の調査。RSS がなく
# ページから取得している媒体と、自動取得を禁止している媒体）
PAUSED_SOURCES = [
    "20 Minuten",
    "Blick",
    "Nau.ch",
    "SWI swissinfo.ch",
    "Watson",
]


def forwards(apps, schema_editor):

    NewsSource = apps.get_model("news", "NewsSource")
    Article = apps.get_model("news", "Article")

    NewsSource.objects.filter(
        name__in=PAUSED_SOURCES,
    ).update(
        is_active=False,
    )

    # 日本語の媒体の紹介文をそのまま出さない。
    # AI が独自の文に書き直すまで一覧には出ない。
    Article.objects.filter(
        original_language="ja",
        ai_processed_at__isnull=True,
    ).update(
        title_ja="",
        summary_ja="",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("news", "0020_article_summary_version_combined"),
    ]

    operations = [
        migrations.RunPython(
            forwards,
            migrations.RunPython.noop,
        ),
    ]
