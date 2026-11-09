"""
2026-11-09
運営の回答に印をつける (回答の数に入れない)。1つの質問に運営の回答がいくつもあるときは、1つにまとめる。
運営の回答 = 運営 (スタッフ) のアカウントの回答、または投稿者なしで名前が「運営」の回答 (0013 で入れたもの)
"""

from django.db import migrations, models
from django.db.models import Q


def forwards(apps, schema_editor):
    Answer = apps.get_model("chiebukuro", "Answer")

    staff = Answer.objects.filter(
        Q(author__is_staff=True) | Q(author__isnull=True, nickname="運営", from_survey=False)
    )
    staff.update(is_staff=True)
    question_ids = set(Answer.objects.filter(is_staff=True).values_list("question_id", flat=True))
    for question_id in question_ids:
        answers = list(Answer.objects.filter(question_id=question_id, is_staff=True).order_by("created_at", "pk"))
        if len(answers) < 2:
            continue
        keep = answers[0]
        keep.body = "\n\n".join(answer.body.strip() for answer in answers if answer.body.strip())
        if not keep.photo_url:
            keep.photo_url = next((answer.photo_url for answer in answers if answer.photo_url), "")
        keep.save(update_fields=["body", "photo_url"])
        Answer.objects.filter(pk__in=[answer.pk for answer in answers[1:]]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("chiebukuro", "0025_nickname_limit"),
    ]

    operations = [
        migrations.AddField(
            model_name="answer",
            name="is_staff",
            field=models.BooleanField(
                default=False,
                help_text="運営の回答は、回答の数に入れません。",
                verbose_name="運営の回答",
            ),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
