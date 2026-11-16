from django.db import migrations
from django.db.models import Max


def stop_bots(apps, schema_editor):
    # 2026-11-16 Taro: 和食・おでかけ・ニュースのBotはやめて、これまでのつぶやきも全部消す (スイスを知ろうBotは残す)
    BotPost = apps.get_model("chiebukuro", "BotPost")
    Post = apps.get_model("chiebukuro", "Post")
    stopped = ["washoku", "outings", "news"]
    BotPost.objects.filter(bot__in=stopped).delete()
    Post.objects.filter(bot__in=stopped).delete()


def survey_dates(apps, schema_editor):
    # 2026-11-16 Taro: アンケートの質問と回答は、本当の日時ではなく、掲示板に出た日 (このマイグレーションの日) に
    import datetime

    from django.utils import timezone

    Question = apps.get_model("chiebukuro", "Question")
    Answer = apps.get_model("chiebukuro", "Answer")
    today = timezone.make_aware(datetime.datetime.combine(timezone.localdate(), datetime.time.min))
    Answer.objects.filter(from_survey=True).update(created_at=today)
    questions = Question.objects.filter(survey_question_id__isnull=False)
    questions.update(created_at=today)
    for question in questions.annotate(latest=Max("answers__created_at")):
        Question.objects.filter(pk=question.pk).update(last_answered_at=question.latest)


class Migration(migrations.Migration):

    dependencies = [
        ("chiebukuro", "0030_question_first"),
    ]

    operations = [
        migrations.RunPython(stop_bots, migrations.RunPython.noop),
        migrations.RunPython(survey_dates, migrations.RunPython.noop),
    ]
