"""
2026-11-05 20:25 (スイス時間) に X から一度に来た20件の匿名訪問を集計から外す。

X に貼られたリンクを自動で開くチェック (普通のパソコン版 Chrome を名乗る) で、人ではない。
これからの分は、ページの JavaScript で人の閲覧かを確かめて外す (0011)。
"""

from django.db import migrations


BOT_VISITORS = [
    "393de7fd-1054-44f8-a8a9-c4a1388e802e",
    "2b076b29-b719-436b-9675-37b05f4c371c",
    "882ddc25-9c11-4a67-a065-fb6516a2dd6e",
    "212c925a-396f-4b5f-8a22-7a78a2fa77cb",
    "3c3e65bb-7ff2-4e28-93c8-d6aff6c51a9e",
    "03252dd1-cca8-4a7b-8b0a-36621f52207d",
    "0775f6e2-0c5f-4307-859c-564ed078a1e9",
    "c4c0cfd5-92c8-4211-8a3e-5fd787fa3efa",
    "ef4f952e-fc45-49bf-93c1-0a36500d63f5",
    "cfde8df3-f3c9-4d58-b2a9-a50133e95881",
    "ca37e68f-829d-468f-be27-cd7a0f71c58d",
    "731cba9b-a955-42a8-8970-f22131df539d",
    "a408ee57-a5e4-4866-b724-5824e3e0597f",
    "29745453-91a5-41f9-9e36-2a73c95546c4",
    "ca5ac7a1-608b-4d64-bafd-d1b22810cca7",
    "c7ec0d99-9442-42c1-acfc-3b55a7012140",
    "3bf85214-55fb-4ace-9696-61bf72ef139b",
    "598388e0-4889-4f8c-a012-1874b036616d",
    "de7ec0a9-55bd-4f74-aa3d-4258d851d830",
    "54dc9cc3-840e-42f0-a9e0-39ea92f9698c",
]


def hide_bots(apps, schema_editor):

    PageView = apps.get_model("usage_analytics", "PageView")

    # 念のため、ログインなしのものだけ
    PageView.objects.filter(
        visitor_id__in=BOT_VISITORS,
        user__isnull=True,
    ).update(is_confirmed=False)


class Migration(migrations.Migration):

    dependencies = [
        ("usage_analytics", "0011_pageview_is_confirmed"),
    ]

    operations = [
        migrations.RunPython(hide_bots, migrations.RunPython.noop),
    ]
