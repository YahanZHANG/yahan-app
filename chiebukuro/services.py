"""
掲示板の中身の計算: ニックネーム、事前アンケートからの取り込み、並べ替え。
"""

from django.db import transaction
from django.db.models import Count, F, Q, Value
from django.db.models.functions import Coalesce

from .models import Answer, Question, Status, SurveyImport


def user_nickname(user):
    """Yapp のニックネーム (なければユーザーID)"""

    if not user or not user.is_authenticated:
        return ""
    from travel.models import UserProfile

    profile = UserProfile.objects.filter(user=user).first()
    return (profile.display_name if profile else user.username)[:30]


# =========================================================
# 事前アンケートからの取り込み
# =========================================================

@transaction.atomic
def import_from_survey():
    """
    事前アンケートの公開中の質問と、公開に同意した答え (非表示でないもの) を取り込む。
    取り込み済みの行 (掲示板で消したものも) は二度と取り込まない。
    戻り値: (質問の数, 答えの数)
    """

    from pre_survey.models import Answer as SurveyAnswer
    from pre_survey.models import Interest as SurveyInterest
    from pre_survey.models import Question as SurveyQuestion

    done_questions = set(SurveyImport.objects.filter(kind="question").values_list("source_id", flat=True))
    done_answers = set(SurveyImport.objects.filter(kind="answer").values_list("source_id", flat=True))

    # アンケートの質問 → 掲示板の質問 (取り込み済みのものも、答えの行き先として使う)
    question_map = {}
    for imported in SurveyImport.objects.filter(kind="question"):
        question_map[imported.source_id] = None
    linked = Question.objects.filter(survey_question_id__isnull=False)
    for question in linked:
        question_map[question.survey_question_id] = question

    new_questions = 0
    survey_questions = SurveyQuestion.objects.filter(status=SurveyQuestion.Status.PUBLISHED).select_related("user")

    for source in survey_questions:
        if source.pk in done_questions:
            continue
        is_staff_question = source.source == SurveyQuestion.Source.STAFF
        question = Question.objects.create(
            body=source.body,
            theme=source.theme,
            region="" if source.region == "other" else source.region,
            source=Question.Source.STAFF if is_staff_question else Question.Source.SURVEY,
            author=source.user,
            nickname="" if is_staff_question else source.nickname,
            survey_question_id=source.pk,
            created_at=source.created_at,
        )
        SurveyImport.objects.create(kind="question", source_id=source.pk)
        question_map[source.pk] = question
        new_questions += 1

    new_answers = 0
    survey_answers = (
        SurveyAnswer.objects
        .filter(publish_consent=True, is_hidden=False, question__status=SurveyQuestion.Status.PUBLISHED)
        .exclude(body="")
        .order_by("created_at")
    )

    for source in survey_answers:
        if source.pk in done_answers:
            continue
        question = question_map.get(source.question_id)
        if question is None:
            continue
        Answer.objects.create(
            question=question,
            body=source.body,
            author=source.user,
            nickname=source.nickname,
            from_survey=True,
            created_at=source.created_at,
        )
        SurveyImport.objects.create(kind="answer", source_id=source.pk)
        new_answers += 1

    # 「私も知りたい」の数と、最後の答えの日時をそろえる
    interest_counts = dict(
        SurveyInterest.objects.values("question_id").annotate(n=Count("pk")).values_list("question_id", "n")
    )
    for question in Question.objects.filter(survey_question_id__isnull=False):
        latest = question.answers.order_by("-created_at").values_list("created_at", flat=True).first()
        count = interest_counts.get(question.survey_question_id, 0)
        if question.survey_interest_count != count or question.last_answered_at != latest:
            Question.objects.filter(pk=question.pk).update(survey_interest_count=count, last_answered_at=latest)

    return new_questions, new_answers


# =========================================================
# 一覧
# =========================================================

SORTS = {
    "new": "新しい答え",
    "wanted": "知りたい人が多い",
    "open": "答え募集中",
}


def question_list(theme="", region="", sort="new", query=""):

    questions = (
        Question.objects
        .filter(status=Status.PUBLISHED)
        .annotate(
            answer_total=Count("answers", filter=Q(answers__status=Status.PUBLISHED), distinct=True),
            interest_total=Count("interests", distinct=True) + F("survey_interest_count"),
        )
    )

    if theme:
        questions = questions.filter(theme=theme)

    if region:
        # 地域を選んだら、その地域の質問と、地域なし (スイス全体) の質問
        questions = questions.filter(Q(region=region) | Q(region=""))

    if query:
        questions = questions.filter(Q(body__icontains=query) | Q(answers__body__icontains=query, answers__status=Status.PUBLISHED)).distinct()

    if sort == "wanted":
        questions = questions.order_by("-interest_total", "-answer_total", "-created_at")
    elif sort == "open":
        questions = questions.filter(answer_total=0).order_by("-interest_total", "-created_at")
    else:
        questions = questions.order_by(Coalesce("last_answered_at", "created_at").desc(nulls_last=True), "-pk")

    return questions


def attach_previews(questions, count=2):
    """各質問に、答えのちら見せ (新しい順に count 件) を付ける"""

    ids = [question.pk for question in questions]
    previews = {}
    for answer in (
        Answer.objects
        .filter(question_id__in=ids, status=Status.PUBLISHED)
        .order_by("question_id", "-created_at")
    ):
        bucket = previews.setdefault(answer.question_id, [])
        if len(bucket) < count:
            bucket.append(answer)
    for question in questions:
        question.previews = previews.get(question.pk, [])
    return questions


# =========================================================
# HOME のタブ
# =========================================================

def best_answers(questions):
    """各質問に、いちばん参考になった答え (なければ最初の答え) を best として付ける"""

    ids = [question.pk for question in questions]
    best = {}
    for answer in (
        Answer.objects
        .filter(question_id__in=ids, status=Status.PUBLISHED)
        .annotate(thanks_total=Count("thanks"))
        .order_by("question_id", "-thanks_total", "created_at")
    ):
        best.setdefault(answer.question_id, answer)
    for question in questions:
        question.best = best.get(question.pk)
    return questions


def popular_questions(theme="", region="", query="", limit=20):
    """人気: 答えがあって、知りたい人・答え・参考になったが多い質問"""

    questions = (
        question_list(theme, region, "new", query)
        .filter(answer_total__gt=0)
        .annotate(thanks_total=Count("answers__thanks", distinct=True))
        .order_by("-interest_total", "-answer_total", "-thanks_total", "-last_answered_at")
    )
    return best_answers(list(questions[:limit]))


def waiting_questions(theme="", region="", query="", limit=30):
    """答え募集中: まだ答えがない質問を、知りたい人が多い順に"""

    return list(question_list(theme, region, "open", query)[:limit])


# =========================================================
# お知らせ (🔔)
# =========================================================

def notify(user, kind, text, url, actor=None):
    """user にお知らせを1件。自分の操作では知らせない。"""

    from .models import Notification

    if user is None or (actor is not None and actor.pk == user.pk):
        return
    Notification.objects.create(
        user=user,
        kind=kind,
        text=text[:200],
        url=url[:300],
        actor=user_nickname(actor) if actor is not None else "",
    )


def unread_notifications(user):
    from .models import Notification

    if not user.is_authenticated:
        return 0
    return Notification.objects.filter(user=user, read_at__isnull=True).count()


def short(text, length=40):
    text = " ".join((text or "").split())
    return text if len(text) <= length else text[:length] + "…"
