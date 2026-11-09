"""
アンケートから取り込んだ質問を、いったん全部「公開待ち」にして、公開の順番をつける。
- 掲示板で (アンケート以外の) 答えがもうついた質問は、そのまま公開
- 答えが2件以上の質問: テーマを順番にまわして、答えの多いもの・「知りたい」の多いものから
- 答えが0〜1件の質問は「答え待ち」の枠 (別に数える): 「知りたい」の多いもの・古いものから
次に掲示板が開かれたとき、それぞれの枠の最初の数 (30問・10問) が公開される (release_survey_questions)。
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
    waiting = []
    for question in candidates:
        if question.board_answers:
            continue
        if question.all_answers <= 1:
            waiting.append(question)
        else:
            by_theme.setdefault(question.theme, []).append(question)
    for questions in by_theme.values():
        questions.sort(key=lambda q: (-q.all_answers, -q.survey_interest_count, q.pk))

    rank = 1
    # 答えのある質問: テーマを順番にまわす (答えの多いテーマから)
    themes = sorted(by_theme, key=lambda theme: -sum(q.all_answers for q in by_theme[theme]))
    while any(by_theme[theme] for theme in themes):
        for theme in themes:
            if by_theme[theme]:
                question = by_theme[theme].pop(0)
                Question.objects.filter(pk=question.pk).update(status="queued", release_rank=rank, release_open=False)
                rank += 1
    # 答え待ちの質問
    waiting.sort(key=lambda q: (-q.survey_interest_count, -q.all_answers, q.pk))
    for question in waiting:
        Question.objects.filter(pk=question.pk).update(status="queued", release_rank=rank, release_open=True)
        rank += 1


def unqueue(apps, schema_editor):
    Question = apps.get_model("chiebukuro", "Question")
    Question.objects.filter(status="queued").update(status="published", release_rank=None, release_open=False)


class Migration(migrations.Migration):

    dependencies = [("chiebukuro", "0021_release_queue")]

    operations = [migrations.RunPython(queue, unqueue)]
