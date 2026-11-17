"""
2026-11-17 Taro: 「募集・告知」に、子ども向けの日本語の会とイベントを運営から載せる。
PBZ Oerlikon の日本語の絵本読み聞かせ (月1〜2回)、レインボーキッズ、Uster ひまわりの会、Uster たまごの会。
掲載は1年 (管理画面で日にちや内容を直せる)。同じタイトルのものがあれば作らない。
"""

from datetime import date, timedelta

from django.conf import settings
from django.db import migrations
from django.utils import timezone

NOTICES = [
    (
        "event",
        "日本語の絵本の読み聞かせ（PBZ Oerlikon・2〜5歳・無料）",
        "チューリッヒ市立図書館 PBZ のエリコン館で、2〜5歳の子どもと親のための、日本語の絵本の読み聞かせ"
        "（Family Literacy Japanisch）が月に1〜2回あります。\n\n"
        "・次回：11月28日（土）10:15〜11:45\n"
        "・参加無料。リンク先のページから申し込みます（名前とメールアドレス。満員のときはキャンセル待ち）\n"
        "・ほかの日にちも、PBZ のイベントのページに出ます",
        "zurich",
        "PBZ Oerlikon（エリコン）",
        date(2026, 11, 28),
        "https://www.pbz.ch/event/family-literacy-japanisch-58/",
    ),
    (
        "friends",
        "レインボーキッズ 会員募集中（0歳〜入園前・毎週金曜）",
        "チューリッヒ市内の GZ Affoltern で、0歳〜入園前のお子さんと親の、日本語のシュピールグルッペとして活動しています。"
        "日本語での読み聞かせ・歌・工作・外遊びを楽しんでいます。見学はいつでもお気軽にどうぞ。\n\n"
        "・毎週金曜日 9:30〜11:00\n"
        "・連絡先：rainbowkids.zh@gmail.com",
        "zurich",
        "GZ Affoltern（チューリッヒ）",
        None,
        "",
    ),
    (
        "friends",
        "Uster ひまわりの会（0歳〜幼稚園入園前）",
        "Uster で、0歳〜幼稚園入園前のお子さんと親が集まる会です。決まったプログラムはなく、のびのび遊んでいます。\n\n"
        "・第2・4・5木曜日の午前\n"
        "・連絡先：himawarinokaiulster@gmail.com",
        "zurich",
        "Uster（ウスター）",
        None,
        "",
    ),
    (
        "friends",
        "Uster たまごの会 会員募集中（2歳〜幼稚園入園前）",
        "日本の歌や遊び、工作、季節の行事を、親子でワイワイ楽しむ会です。見学をお待ちしています。\n\n"
        "・第1・第3水曜日 9:30〜11:30\n"
        "・2歳から幼稚園入園前まで\n"
        "・連絡先：ulster.tamago@gmail.com",
        "zurich",
        "Uster（ウスター）",
        None,
        "http://ulstertamago.wordpress.com",
    ),
]


def forwards(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    Notice = apps.get_model("chiebukuro", "Notice")
    owner = (User.objects.filter(is_superuser=True).order_by("pk").first()
             or User.objects.filter(is_staff=True).order_by("pk").first())
    if owner is None:
        return
    now = timezone.now()
    for minutes, (kind, title, body, region, place, event_date, link) in enumerate(NOTICES):
        if Notice.objects.filter(title=title).exists():
            continue
        Notice.objects.create(
            kind=kind,
            title=title,
            body=body,
            region=region,
            place=place,
            event_date=event_date,
            link=link,
            owner=owner,
            nickname="運営",
            expires_at=now + timedelta(days=365),
            created_at=now - timedelta(minutes=minutes),
        )


class Migration(migrations.Migration):
    dependencies = [("chiebukuro", "0034_remove_survey_items")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
