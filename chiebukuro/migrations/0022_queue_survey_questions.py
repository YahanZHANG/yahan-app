"""
アンケートから取り込んだ質問を、いったん全部「公開待ち」にして、公開の順番をつける。
- 掲示板で (アンケート以外の) 答えがもうついた質問は、そのまま公開
- 答えが1件以下の質問も、そのまま公開 (答えを集めたいので。順番なし = 30問には数えない)
- ほかは、テーマを順番にまわして、答えの多いもの・「知りたい」の多いものから
最初の30問は、次に掲示板が開かれたときに公開される (release_survey_questions)。
"""

from django.db import migrations
from django.db.models import Count, Q


def queue(apps, schema_editor):
    Question = apps.get_model("chiebukuro", "Question")

    candidates = (
        Question.objects.filter(survey_question_id__isnull=False, status="published")
        .annotate(
            board_answers=Count("answers", filter=Q(answers__status="published", answers__from_survey=False)),
            all_answers=Count("answers", filter=Q(answers__status="published")),
        )
    )
    by_theme = {}
    for question in candidates:
        if question.board_answers or question.all_answers <= 1:
            continue
        by_theme.setdefault(question.theme, []).append(question)
    for questions in by_theme.values():
        questions.sort(key=lambda q: (-q.all_answers, -q.survey_interest_count, q.pk))

    # テーマを順番にまわす (答えの多いテーマから)
    themes = sorted(by_theme, key=lambda theme: -sum(q.all_answers for q in by_theme[theme]))
    rank = 1
    while any(by_theme[theme] for theme in themes):
        for theme in themes:
            if by_theme[theme]:
                question = by_theme[theme].pop(0)
                Question.objects.filter(pk=question.pk).update(status="queued", release_rank=rank)
                rank += 1


def unqueue(apps, schema_editor):
    Question = apps.get_model("chiebukuro", "Question")
    Question.objects.filter(status="queued").update(status="published", release_rank=None)


class Migration(migrations.Migration):

    dependencies = [("chiebukuro", "0021_release_queue")]

    operations = [migrations.RunPython(queue, unqueue)]
