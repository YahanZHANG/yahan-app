"""
事前アンケートの中身: 同意文、ブラウザの目印、ニックネーム、質問を出す順番。
"""

import random
import re
import uuid
from functools import lru_cache
from pathlib import Path

from django.contrib.auth import get_user_model
from django.db.models import BooleanField, Case, Count, Exists, OuterRef, Q, Value, When

from .models import Answer, Interest, Participant, Question, Skip


# =========================================================
# 同意文 (consent/v1.txt, v2.txt ... の一番新しいもの)
# =========================================================

CONSENT_DIR = Path(__file__).resolve().parent / "consent"


def _version_number(path):
    match = re.fullmatch(r"v(\d+)", path.stem)
    return int(match.group(1)) if match else -1


@lru_cache(maxsize=1)
def current_consent():
    """(バージョン名, 文面)。文面を差し替えるときは v2.txt を足す。"""

    files = sorted(CONSENT_DIR.glob("v*.txt"), key=_version_number)
    latest = files[-1]
    return latest.stem, latest.read_text(encoding="utf-8").strip()


def consent_blocks(text):
    """同意文を段落に分ける。「# 」で始まる段落は見出し、「※」で始まる段落 (メモ) は出さない。"""

    blocks = []
    for paragraph in text.split("\n\n"):
        paragraph = paragraph.strip()
        if not paragraph or paragraph.startswith("※"):
            continue
        if paragraph.startswith("# "):
            blocks.append({"heading": True, "text": paragraph[2:].strip()})
        else:
            blocks.append({"heading": False, "text": paragraph})
    return blocks


# =========================================================
# ブラウザの目印 (cookie)
# =========================================================

TOKEN_COOKIE = "pre_survey_token"
TOKEN_MAX_AGE = 60 * 60 * 24 * 365 * 2


def browser_token(request):
    """このブラウザの目印。なければ作り、レスポンスで cookie に保存する (views.with_token)。"""

    cached = getattr(request, "_pre_survey_token", None)
    if cached:
        return cached

    try:
        token = uuid.UUID(request.COOKIES.get(TOKEN_COOKIE, ""))
    except ValueError:
        token = uuid.uuid4()
        request._pre_survey_new_token = True

    request._pre_survey_token = token
    return token


def identity(request):
    """「この人の記録」を探す条件: このブラウザの記録と、ログイン中ならそのユーザーの記録"""

    condition = Q(browser_token=browser_token(request))
    if request.user.is_authenticated:
        condition |= Q(user=request.user)
    return condition


def owner_fields(request, participant):
    """記録を作るときに入れる「だれの記録か」"""

    return {
        "user": request.user if request.user.is_authenticated else None,
        "browser_token": browser_token(request),
        "participant": participant,
    }


# =========================================================
# 運営におまかせのニックネーム
# =========================================================

# 3つのテイスト。どのセットも同じ確率で選び、前と後ろは同じセットの中で組み合わせる
# (10×10×3 = 300通り)
NICKNAME_SETS = [
    # 食べもの系 (ゆるくてかわいい)
    (
        ["ほかほか", "もちもち", "ふわふわ", "さくさく", "とろとろ",
         "ほくほく", "ぷるぷる", "こんがり", "つやつや", "あつあつ"],
        ["おにぎり", "おだんご", "メロンパン", "たまご焼き", "おもち",
         "肉まん", "プレッツェル", "ラクレット", "ロスティ", "クロワッサン"],
    ),
    # 自然・季節系 (しっとり、詩的)
    (
        ["春風の", "月夜の", "朝霧の", "夕焼けの", "星降る",
         "木漏れ日の", "初雪の", "雨上がりの", "そよ風の", "小春日和の"],
        ["旅人", "詩人", "カフェ", "ベンチ", "ピアノ",
         "ランプ", "手紙", "ことり", "灯台", "ひつじ"],
    ),
    # 動物のお仕事系 (ちょっとユーモア)
    (
        ["くま", "ねこ", "ペンギン", "パンダ", "カワウソ",
         "アルパカ", "ハムスター", "コアラ", "ラッコ", "シロクマ"],
        ["店長", "先生", "隊長", "博士", "パン屋",
         "郵便屋", "船長", "庭師", "探検家", "料理長"],
    ),
]

# すでに使われている名前を避けて選び直す回数 (全部使われていたら重なってもよい)
NICKNAME_TRIES = 30


def _nickname_candidate():
    heads, tails = random.choice(NICKNAME_SETS)
    return random.choice(heads) + random.choice(tails)


def random_nickname(avoid=""):
    """
    運営におまかせのニックネーム。ほかの参加者が使っている名前と、
    いま表示している名前 (avoid、「ほかの名前にする」のとき) はなるべく避ける。
    """

    used = set(
        Participant.objects
        .filter(nickname_mode=Participant.NicknameMode.AUTO)
        .exclude(nickname="")
        .values_list("nickname", flat=True)
    )
    if avoid:
        used.add(avoid)

    name = _nickname_candidate()
    for _ in range(NICKNAME_TRIES):
        if name not in used:
            break
        name = _nickname_candidate()
    return name


# =========================================================
# 質問を出す順番
# =========================================================

# 何問に1回、人気の質問を混ぜるか (3なら 3問目・6問目・9問目…)
POPULAR_EVERY = 3

# 「私も知りたい」がこの票数以上なら人気の質問
POPULAR_MIN_INTERESTS = 2

# 回答がこの数以上集まった質問は、ほかの質問を全部見たあとにだけ出す (足りない質問を優先)
ENOUGH_ANSWERS = 3


def next_question(request, participant):
    """
    次に出す質問。なければ None (すべての公開中の質問を、この参加で見終わったときだけ)。

    - 公開中の質問すべてが対象。ほかの人がもう答えた質問も出す (いろいろな人の意見を集めるため)
    - 選んだテーマの質問を先に出し、それが尽きたら、ほかのテーマの質問も出す
    - 自分が回答した質問、自分が追加した質問は出さない
    - この参加でスキップ・「知りたい」にした質問は出さない
    - 前の参加でスキップ・「知りたい」にした質問は、まだ見ていない質問の後
    - 地域つきの質問は、地域を選んでいない人か、同じ地域の人にだけ
    - 回答が ENOUGH_ANSWERS 件以上集まった質問は、テーマに関係なくいちばん後
    - その中で、回答の少ない順 (0件が先) → 新しい順
    - ただし POPULAR_EVERY 問に1回は、「私も知りたい」が POPULAR_MIN_INTERESTS 票以上の
      人気の質問を、テーマに関係なく出す (知りたい票の多い順 → 回答の少ない順)
    """

    mine = identity(request)

    answered = Answer.objects.filter(mine).values("question_id")
    passed_now = Skip.objects.filter(participant=participant).values("question_id")
    interested_now = Interest.objects.filter(participant=participant).values("question_id")
    own = Question.objects.filter(mine).values("pk")

    seen_before = (
        Skip.objects.filter(mine, question=OuterRef("pk"))
        .exclude(participant=participant)
    )
    interested_before = (
        Interest.objects.filter(mine, question=OuterRef("pk"))
        .exclude(participant=participant)
    )

    questions = (
        Question.objects
        .filter(status=Question.Status.PUBLISHED)
        .exclude(pk__in=answered)
        .exclude(pk__in=passed_now)
        .exclude(pk__in=interested_now)
        .exclude(pk__in=own)
    )

    if participant.region:
        questions = questions.filter(Q(region="") | Q(region=participant.region))

    shown_count = (
        Answer.objects.filter(participant=participant).count()
        + Skip.objects.filter(participant=participant).count()
        + Interest.objects.filter(participant=participant).count()
    )

    if shown_count % POPULAR_EVERY == POPULAR_EVERY - 1:
        popular = (
            questions
            .exclude(pk__in=Interest.objects.filter(mine).values("question_id"))
            .exclude(pk__in=Skip.objects.filter(mine).values("question_id"))
            .annotate(
                interest_total=Count("interests", distinct=True),
                answer_count=Count("answers", filter=Q(answers__is_hidden=False), distinct=True),
            )
            .filter(interest_total__gte=POPULAR_MIN_INTERESTS, answer_count__lt=ENOUGH_ANSWERS)
            .order_by("-interest_total", "answer_count", "-created_at", "-pk")
            .first()
        )
        if popular is not None:
            return popular

    return (
        questions
        .annotate(
            other_theme=Case(
                When(theme__in=participant.themes, then=Value(False)),
                default=Value(True),
                output_field=BooleanField(),
            ),
            answer_count=Count("answers", filter=Q(answers__is_hidden=False)),
            skipped_before=Exists(seen_before),
            interested_before=Exists(interested_before),
        )
        .annotate(
            enough=Case(
                When(answer_count__gte=ENOUGH_ANSWERS, then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            ),
        )
        .order_by("enough", "other_theme", "skipped_before", "interested_before", "answer_count", "-created_at", "-pk")
        .first()
    )


# =========================================================
# 終了画面での登録: ユーザーIDの初期値
# =========================================================

def suggest_username(nickname):
    """
    ニックネームから、使えるユーザーIDの案を作る。(案, 元のニックネームがすでに使われていたか)
    ユーザーIDに使えない文字 (空白・記号など) は取り除く。何も残らなければ ("", False)。
    """

    base = re.sub(r"[^\w.@+-]", "", nickname or "")[:140]

    if not base:
        return "", False

    users = get_user_model().objects

    if not users.filter(username__iexact=base).exists():
        return base, False

    for number in range(2, 100):
        candidate = f"{base}{number}"
        if not users.filter(username__iexact=candidate).exists():
            return candidate, True

    return f"{base}{random.randint(1000, 9999)}", True
