"""
事前アンケート (pre-survey)

スイス在住日本人向け掲示板の公開前に、質問と回答を集める。
ここで集めた質問・回答は、将来の掲示板でもそのまま使えるように作ってある。

「だれの記録か」は、ログインしている人はユーザー、していない人は
ブラウザごとの目印 (browser_token, cookie) で見分ける。ログインしている人の
記録にも browser_token は残すので、あとから登録した人の記録もつなげられる。
"""

from django.conf import settings
from django.db import models


class Theme(models.TextChoices):
    LIFE = "life", "生活"
    SHOPPING = "shopping", "買い物"
    CHILDCARE = "childcare", "育児"
    WORK = "work", "仕事"
    LANGUAGE = "language", "語学"
    OUTING = "outing", "おでかけ"
    HEALTH = "health", "健康・美容"
    MONEY = "money", "お金"
    CULTURE = "culture", "人付き合い・文化"
    # 質問を追加するとき、どのテーマにも当てはまらないもの (回答するテーマとしては選ばない)
    OTHER = "other", "その他"


# 回答するテーマとして選べるもの (「その他」の質問は、選んだテーマの質問の後に出る)
ANSWER_THEMES = [(value, label) for value, label in Theme.choices if value != Theme.OTHER]


# SwissNews の地域 (news.Region の slug) と同じ分類。ドイツ語圏を上にしている。
REGION_CHOICES = [
    ("zurich", "チューリッヒ"),
    ("winterthur", "ヴィンタートゥール"),
    ("zug", "ツーク"),
    ("basel", "バーゼル"),
    ("bern", "ベルン"),
    ("lucerne", "ルツェルン"),
    ("st-gallen", "ザンクトガレン"),
    ("aarau-aargau", "アーラウ・アールガウ"),
    ("schaffhausen", "シャフハウゼン"),
    ("solothurn", "ゾロトゥルン"),
    ("thun", "トゥーン"),
    ("chur-graubuenden", "クール・グラウビュンデン"),
    ("biel-bienne", "ビール/ビエンヌ"),
    ("fribourg", "フリブール"),
    ("geneva", "ジュネーブ"),
    ("lausanne-vaud", "ローザンヌ・ヴォー"),
    ("neuchatel", "ヌーシャテル"),
    ("sion-valais", "シオン・ヴァレー"),
    ("lugano-ticino", "ルガーノ・ティチーノ"),
    ("other", "その他"),
]


ANONYMOUS_NAME = "名無しさん"


class Participant(models.Model):
    """1回の参加 (終了画面の「さらに他の質問に答える」で新しい行ができる)"""

    class NicknameMode(models.TextChoices):
        CUSTOM = "custom", "自分で設定"
        AUTO = "auto", "運営におまかせ"
        ANONYMOUS = "anonymous", "名無し"

    browser_token = models.UUIDField("ブラウザの目印", db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ユーザー",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pre_survey_participations",
    )
    nickname = models.CharField("ニックネーム", max_length=30, blank=True)
    nickname_mode = models.CharField(
        "ニックネームの決め方",
        max_length=20,
        choices=NicknameMode.choices,
        blank=True,
    )
    themes = models.JSONField("テーマ", default=list, blank=True)
    region = models.CharField("地域", max_length=30, choices=REGION_CHOICES, blank=True)
    consent_version = models.CharField("同意した文面のバージョン", max_length=30)
    consented_at = models.DateTimeField("同意日時")
    created_at = models.DateTimeField("参加日時", auto_now_add=True)
    finished_at = models.DateTimeField("終了日時", null=True, blank=True)

    class Meta:
        verbose_name = "参加"
        verbose_name_plural = "参加"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.display_name} ({self.created_at:%Y-%m-%d %H:%M})"

    @property
    def display_name(self):
        return self.nickname or ANONYMOUS_NAME

    def theme_labels(self):
        labels = dict(Theme.choices)
        return [labels[key] for key in self.themes if key in labels]


class Question(models.Model):

    class Source(models.TextChoices):
        STAFF = "staff", "運営"
        MEMBER = "member", "利用者"

    class Status(models.TextChoices):
        PENDING = "pending", "承認待ち"
        PUBLISHED = "published", "公開"
        HIDDEN = "hidden", "非公開"
        REJECTED = "rejected", "却下"

    body = models.TextField("質問")
    theme = models.CharField("テーマ", max_length=20, choices=Theme.choices)
    region = models.CharField("地域", max_length=30, choices=REGION_CHOICES, blank=True)
    source = models.CharField("作成者", max_length=10, choices=Source.choices, default=Source.STAFF)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ユーザー",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pre_survey_questions",
    )
    participant = models.ForeignKey(
        Participant,
        verbose_name="参加",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="questions",
    )
    browser_token = models.UUIDField("ブラウザの目印", null=True, blank=True, db_index=True)
    nickname = models.CharField("ニックネーム", max_length=30, blank=True)
    # 利用者の質問はすぐ公開。おかしいものだけ管理画面で非公開・却下にする。
    status = models.CharField(
        "ステータス",
        max_length=20,
        choices=Status.choices,
        default=Status.PUBLISHED,
        db_index=True,
    )
    # 運営の質問を JSON から取り込むときの目印 (同じ質問を2回入れないため)
    seed_key = models.CharField("取り込みキー", max_length=50, unique=True, null=True, blank=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        verbose_name = "質問"
        verbose_name_plural = "質問"
        ordering = ["-created_at"]

    def __str__(self):
        return self.body[:40]

    @property
    def display_name(self):
        if self.source == self.Source.STAFF:
            return "運営"
        return self.nickname or ANONYMOUS_NAME


class Answer(models.Model):

    question = models.ForeignKey(
        Question,
        verbose_name="質問",
        on_delete=models.CASCADE,
        related_name="answers",
    )
    body = models.TextField("回答")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ユーザー",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pre_survey_answers",
    )
    participant = models.ForeignKey(
        Participant,
        verbose_name="参加",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="answers",
    )
    browser_token = models.UUIDField("ブラウザの目印", null=True, blank=True, db_index=True)
    nickname = models.CharField("ニックネーム", max_length=30, blank=True)
    publish_consent = models.BooleanField("公開に同意", default=False)
    is_hidden = models.BooleanField("非表示", default=False)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)

    class Meta:
        verbose_name = "回答"
        verbose_name_plural = "回答"
        ordering = ["-created_at"]

    def __str__(self):
        return self.body[:40]

    @property
    def display_name(self):
        return self.nickname or ANONYMOUS_NAME


class Interest(models.Model):
    """「私も知りたい」"""

    question = models.ForeignKey(
        Question,
        verbose_name="質問",
        on_delete=models.CASCADE,
        related_name="interests",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ユーザー",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pre_survey_interests",
    )
    participant = models.ForeignKey(
        Participant,
        verbose_name="参加",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="interests",
    )
    browser_token = models.UUIDField("ブラウザの目印", null=True, blank=True, db_index=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)

    class Meta:
        verbose_name = "私も知りたい"
        verbose_name_plural = "私も知りたい"
        ordering = ["-created_at"]


class Skip(models.Model):
    """
    スキップ。同じ参加の中ではその質問を出さない。
    次の参加では出すが、まだ見ていない質問より後にする。
    """

    question = models.ForeignKey(
        Question,
        verbose_name="質問",
        on_delete=models.CASCADE,
        related_name="skips",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ユーザー",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pre_survey_skips",
    )
    participant = models.ForeignKey(
        Participant,
        verbose_name="参加",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="skips",
    )
    browser_token = models.UUIDField("ブラウザの目印", null=True, blank=True, db_index=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)

    class Meta:
        verbose_name = "スキップ"
        verbose_name_plural = "スキップ"
        ordering = ["-created_at"]

