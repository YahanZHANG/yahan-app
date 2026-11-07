"""
2026-11-07
1. 事前アンケートで利用者が追加した質問の文面を整える (アンケートと掲示板の両方)
2. 運営の質問と重なる利用者の質問は、答えを運営の質問へ移して非公開にする
3. 友人の先行テスト用に、運営の質問 (健康) と運営の答えを入れる (利用者がいる DB だけ)
"""

from django.conf import settings
from django.db import migrations
from django.utils import timezone


# (本文の書き出し, 新しい本文, 新しいテーマ or None)
POLISH = [
    ("時短でも美味しく食べられる", "忙しい日でも手早くおいしく作れる、スイスでの定番ごはんはありますか？（つい毎日パスタになってしまいます）", None),
    ("市内でトイレに行きたくなった", "街なかで急にトイレに行きたくなったとき、どこのトイレを使っていますか？探し方のコツはありますか？", None),
    ("スイスのプールって寒いところばかり", "スイスのプールは水が冷たいところが多いですが、温かいプールや、子どもと行きやすいおすすめのプールはありますか？", None),
    ("日本の電話番号持ってる", "スイスに住んでからも、日本の電話番号を持っていますか？おすすめの方法やサービスはありますか？", None),
    ("日本のアットコスメアプリのような", "日本の@cosmeのように、化粧品や日用品の人気ランキングがわかるサイトやアプリはありますか？ここでおすすめを教えてもらえるのも大歓迎です。", None),
    ("定年後もスイスに住み続ける", "定年後もスイスに住み続ける予定ですか？それとも日本に帰りたいですか？", None),
    ("自炊の際、日本食を作ることが多い", "自炊では、日本食と現地の料理、どちらを作ることが多いですか？", None),
    ("スイスでの年金生活って余裕", "スイスでの年金生活、お金に余裕はありそうですか？老後に向けて準備していることはありますか？", "money"),
    ("ドイツ語を独学するのに良かった", "ドイツ語を独学するとき、役に立った参考書や教材はありますか？", None),
]

# (本文の書き出し, 重なる運営の質問の seed_key)
DUPLICATES = [
    ("日本で買ってスイスに持って帰ってくる", "q18"),
    ("日本に帰国の際、お土産って", "q19"),
    ("おすすめの求人サイトって", "q31"),
    ("仕事、どうやって見つけましたか", "q31"),
    ("日本人でも行ける美容院って", "q17"),
    ("オススメのドイツ語語学学校", "q34"),
    ("チューリッヒで日本語が通じる、または通じなくてもオススメの歯医者", "q05"),
]

TEST_QUESTIONS = [
    (
        "冬のスイスは日が短くて暗い日が続きますが、気分が沈まないように、どんな工夫をしていますか？",
        [
            "晴れた日は、昼休みに15分でも外を歩くようにしています。平地が霧で真っ白な日でも、少し高い山に上がると霧の上に出て、青空が見えることがよくあります（Nebelmeer）。天気予報アプリで、霧の上限の高さを見てから出かけると当たりやすいです。",
            "冬は日光が少ないので、ビタミンDを気にする人が多いです。足りているかどうかは、かかりつけ医の血液検査でわかります。サプリを飲むときは、量を医師や薬局で相談すると安心です。",
            "朝に明るい光を浴びると、体内時計が整いやすいと言われています。家電店や通販では、朝に使う明るいライト（Tageslichtlampe）も売られています。",
        ],
    ),
    (
        "スイスで日焼け止めを買うなら、どれがおすすめですか？山や雪の上でも使えるものを知りたいです。",
        [
            "山の上や雪の上は、平地より紫外線がずっと強くなります。ハイキングやスキーのときは、SPF50の日焼け止めを、汗をかいたらこまめに塗り直すのが基本です。",
            "スーパーでは、Migros の Sun Look など手ごろなものがあります。肌が敏感な人は、薬局（Apotheke）で相談すると、肌に合うものを出してもらえます。",
            "使い慣れた日本の日焼け止めは、一時帰国のときにまとめて買って帰る人も多いです。",
        ],
    ),
    (
        "スイスで婦人科（Frauenarzt）を探すとき、どうやって見つけましたか？",
        [
            "OneDoc や Doctena などの予約サイトでは、話せる言葉で医師を絞りこめるものがあります。英語で診てもらえるところも見つかります。",
            "健康保険の種類（かかりつけ医が先に診るタイプなど）によっては、先にかかりつけ医の紹介が必要なことがあります。予約の前に、保険の条件を確かめておくと安心です。",
        ],
    ),
    (
        "子どもの予防接種、スイスと日本でスケジュールが違いますが、どうやって確かめていますか？",
        [
            "スイスの予防接種の予定は、連邦保健庁（BAG）の「スイス予防接種計画」にまとまっています。小児科に母子手帳を持っていくと、日本で受けた分と照らし合わせてもらえます。",
            "スイスでは、接種の記録を「Impfausweis」という手帳に書いてもらいます。日本に帰る予定がある家庭は、日本の予定との違いを、帰国前に日本の小児科にも相談しておくと安心です。",
        ],
    ),
]


def forwards(apps, schema_editor):
    SurveyQuestion = apps.get_model("pre_survey", "Question")
    SurveyAnswer = apps.get_model("pre_survey", "Answer")
    Question = apps.get_model("chiebukuro", "Question")
    Answer = apps.get_model("chiebukuro", "Answer")
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))

    members = SurveyQuestion.objects.filter(source="member")

    for start, body, theme in POLISH:
        for source in members.filter(body__startswith=start):
            source.body = body
            if theme:
                source.theme = theme
            source.save(update_fields=["body", "theme"] if theme else ["body"])
            fields = {"body": body}
            if theme:
                fields["theme"] = theme
            Question.objects.filter(survey_question_id=source.pk).update(**fields)

    for start, seed_key in DUPLICATES:
        target = SurveyQuestion.objects.filter(seed_key=seed_key).first()
        if target is None:
            continue
        board_target = Question.objects.filter(survey_question_id=target.pk).first()
        for source in members.filter(body__startswith=start):
            SurveyAnswer.objects.filter(question=source).update(question=target)
            source.status = "hidden"
            source.save(update_fields=["status"])
            board_source = Question.objects.filter(survey_question_id=source.pk).first()
            if board_source is None:
                continue
            if board_target is not None:
                Answer.objects.filter(question=board_source).update(question=board_target)
                latest = Answer.objects.filter(question=board_target).order_by("-created_at").values_list("created_at", flat=True).first()
                Question.objects.filter(pk=board_target.pk).update(last_answered_at=latest)
            board_source.status = "hidden"
            board_source.save(update_fields=["status"])

    if not User.objects.exists():
        return
    now = timezone.now()
    for body, answers in TEST_QUESTIONS:
        if Question.objects.filter(body=body).exists():
            continue
        question = Question.objects.create(body=body, theme="health", source="staff", created_at=now)
        for text in answers:
            Answer.objects.create(question=question, body=text, nickname="運営", created_at=now)
        Question.objects.filter(pk=question.pk).update(last_answered_at=now)


class Migration(migrations.Migration):

    dependencies = [
        ("chiebukuro", "0012_preview_key"),
        ("pre_survey", "0003_share_offer"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
