"""
これまでの記録 (公開Swiss News・ログインユーザーの利用履歴) を
新しい PageView にコピーする。元の表はそのまま残す。
"""

import uuid
from datetime import timedelta

from django.db import migrations

from usage_analytics.sources import classify_source


BATCH_SIZE = 2000

VISIT_GAP = timedelta(minutes=30)

OWN_HOSTS = ("yahan-app.onrender.com",)

# ログインユーザーの過去データには cookie が無いので、ユーザーごとに固定のIDを作る
LEGACY_USER_NAMESPACE = uuid.UUID("6b1f3c1e-2f0d-4b8a-9a52-3d7f0c9e4a11")

DEFAULT_EXCLUDED_USERNAMES = ("admin", "yahan", "fumimasakubo")


def copy_public_news(PublicNewsEvent, PageView):

    rows = (
        PublicNewsEvent.objects
        .order_by("visitor_id", "accessed_at", "id")
        .values(
            "visitor_id",
            "visit_id",
            "path",
            "accessed_at",
            "is_visit_start",
            "referrer_host",
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "device_type",
        )
    )

    batch = []
    previous_visitor = None
    previous_time = None
    previous_visit = None

    for row in rows.iterator(chunk_size=BATCH_SIZE):

        is_first_of_visitor = row["visitor_id"] != previous_visitor

        visit_id = row["visit_id"]

        if visit_id:
            is_visit_start = is_first_of_visitor or visit_id != previous_visit
        else:
            is_visit_start = (
                is_first_of_visitor
                or row["accessed_at"] - previous_time > VISIT_GAP
            )
            visit_id = uuid.uuid4() if is_visit_start else previous_visit

        source_type = source_label = ""

        if is_visit_start:
            source_type, source_label = classify_source(
                row["referrer_host"],
                row["utm_source"],
                OWN_HOSTS,
            )

        batch.append(
            PageView(
                visitor_id=row["visitor_id"],
                visit_id=visit_id,
                app_key="news",
                path=(row["path"] or "")[:300],
                accessed_at=row["accessed_at"],
                is_visit_start=is_visit_start,
                is_new_visitor=is_first_of_visitor,
                source_type=source_type,
                source_label=source_label,
                referrer_host=row["referrer_host"] if is_visit_start else "",
                utm_source=row["utm_source"] if is_visit_start else "",
                utm_medium=row["utm_medium"] if is_visit_start else "",
                utm_campaign=row["utm_campaign"] if is_visit_start else "",
                device_type=row["device_type"] or "other",
            )
        )

        previous_visitor = row["visitor_id"]
        previous_time = row["accessed_at"]
        previous_visit = visit_id

        if len(batch) >= BATCH_SIZE:
            PageView.objects.bulk_create(batch)
            batch = []

    if batch:
        PageView.objects.bulk_create(batch)


def copy_signed_in(UsageEvent, UserNewsEvent, PageView):

    user_ids = set(
        UsageEvent.objects.values_list("user_id", flat=True).distinct()
    ) | set(
        UserNewsEvent.objects.values_list("user_id", flat=True).distinct()
    )

    for user_id in sorted(user_ids):

        # News はページ単位の記録 (UserNewsEvent) があるのでそちらを使う
        events = [
            (accessed_at, app_key, f"/{app_key}/" if app_key != "portal" else "/")
            for accessed_at, app_key in (
                UsageEvent.objects
                .filter(user_id=user_id)
                .exclude(app_key="news")
                .values_list("accessed_at", "app_key")
            )
        ] + [
            (accessed_at, "news", path or "/news/")
            for accessed_at, path in (
                UserNewsEvent.objects
                .filter(user_id=user_id)
                .values_list("accessed_at", "path")
            )
        ]

        events.sort(key=lambda event: event[0])

        visitor_id = uuid.uuid5(LEGACY_USER_NAMESPACE, f"user:{user_id}")

        batch = []
        previous_time = None
        visit_id = None

        for index, (accessed_at, app_key, path) in enumerate(events):

            is_visit_start = (
                previous_time is None
                or accessed_at - previous_time > VISIT_GAP
            )

            if is_visit_start:
                visit_id = uuid.uuid4()

            batch.append(
                PageView(
                    visitor_id=visitor_id,
                    visit_id=visit_id,
                    user_id=user_id,
                    app_key=app_key,
                    path=path[:300],
                    accessed_at=accessed_at,
                    is_visit_start=is_visit_start,
                    is_new_visitor=index == 0,
                    source_type="unknown" if is_visit_start else "",
                    source_label="記録なし" if is_visit_start else "",
                )
            )

            previous_time = accessed_at

            if len(batch) >= BATCH_SIZE:
                PageView.objects.bulk_create(batch)
                batch = []

        if batch:
            PageView.objects.bulk_create(batch)


def forwards(apps, schema_editor):

    PageView = apps.get_model("usage_analytics", "PageView")

    # 二重コピー防止
    if PageView.objects.exists():
        return

    copy_public_news(
        apps.get_model("usage_analytics", "PublicNewsEvent"),
        PageView,
    )

    copy_signed_in(
        apps.get_model("usage_analytics", "UsageEvent"),
        apps.get_model("usage_analytics", "UserNewsEvent"),
        PageView,
    )

    User = apps.get_model("auth", "User")
    AnalyticsExclusion = apps.get_model("usage_analytics", "AnalyticsExclusion")

    for user in User.objects.filter(username__in=DEFAULT_EXCLUDED_USERNAMES):
        AnalyticsExclusion.objects.get_or_create(user=user)


def backwards(apps, schema_editor):

    apps.get_model("usage_analytics", "PageView").objects.all().delete()
    apps.get_model("usage_analytics", "AnalyticsExclusion").objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("usage_analytics", "0007_pageview"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
