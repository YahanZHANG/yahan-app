"""
スイス生活の知恵袋 (スイス在住日本人の掲示板)

- 質問と答え (知恵袋): 事前アンケートの質問・回答 (公開に同意したもの) が最初の中身
- つぶやき: 短い書き込み。返信と「役に立った」
- ゆずりあい: ゆずります・ください・貸します・借りたい (お金のやりとりはしない)
- 募集・告知: お店・教室・イベント・仲間・シッター。1人1件、30日で自動で終わる
- 品物と告知には、出した人と送った人の2人だけのやりとり (ItemRequest + Message)。
  連絡先は公開しない。
- お知らせ (Notification): 答え・返信・やりとりが届いたら、右上の🔔に出る
"""

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from pre_survey.models import REGION_CHOICES, Theme


THEME_CHOICES = [(value, label) for value, label in Theme.choices]

# 掲示板で選ぶ地域 (アンケートと同じ分類。「その他」は使わず、空 = スイス全体)
BOARD_REGION_CHOICES = [(value, label) for value, label in REGION_CHOICES if value != "other"]


class BoardSettings(models.Model):
    """掲示板の設定 (1行だけ)"""

    is_open = models.BooleanField(
        "公開する",
        default=False,
        help_text="オフの間は、運営 (スタッフ) だけが見られます。ほかの人には「準備中」の画面が出ます。",
    )
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        verbose_name = "掲示板の設定"
        verbose_name_plural = "掲示板の設定"

    def __str__(self):
        return "掲示板の設定"

    @classmethod
    def current(cls):
        settings_row, _ = cls.objects.get_or_create(pk=1)
        return settings_row


class Status(models.TextChoices):
    PUBLISHED = "published", "公開"
    HIDDEN = "hidden", "非公開"


class Question(models.Model):

    class Source(models.TextChoices):
        MEMBER = "member", "利用者"
        STAFF = "staff", "運営"
        SURVEY = "survey", "事前アンケート"

    body = models.TextField("質問")
    theme = models.CharField("テーマ", max_length=20, choices=THEME_CHOICES, default=Theme.LIFE)
    region = models.CharField("地域", max_length=30, choices=BOARD_REGION_CHOICES, blank=True)
    source = models.CharField("作成者", max_length=10, choices=Source.choices, default=Source.MEMBER)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="投稿者",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chie_questions",
    )
    nickname = models.CharField("ニックネーム", max_length=30, blank=True)
    status = models.CharField("ステータス", max_length=20, choices=Status.choices, default=Status.PUBLISHED, db_index=True)
    # アンケートで押された「私も知りたい」(取り込み時の数。掲示板で押された分は Interest)
    survey_interest_count = models.PositiveIntegerField("アンケートでの「知りたい」", default=0)
    # 事前アンケートの質問 (取り込み元)
    survey_question_id = models.PositiveIntegerField("アンケートの質問ID", null=True, blank=True, unique=True)
    # 新しい答えがついた日時 (HOME の「新しい答え順」)
    last_answered_at = models.DateTimeField("最後の答え", null=True, blank=True, db_index=True)
    created_at = models.DateTimeField("作成日時", default=timezone.now, db_index=True)
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
        return self.nickname or "名無しさん"


class Answer(models.Model):

    question = models.ForeignKey(Question, verbose_name="質問", on_delete=models.CASCADE, related_name="answers")
    body = models.TextField("答え")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="投稿者",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chie_answers",
    )
    nickname = models.CharField("ニックネーム", max_length=30, blank=True)
    from_survey = models.BooleanField("事前アンケートから", default=False)
    status = models.CharField("ステータス", max_length=20, choices=Status.choices, default=Status.PUBLISHED, db_index=True)
    created_at = models.DateTimeField("作成日時", default=timezone.now)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        verbose_name = "答え"
        verbose_name_plural = "答え"
        ordering = ["created_at"]

    def __str__(self):
        return self.body[:40]

    @property
    def display_name(self):
        return self.nickname or "名無しさん"


class Interest(models.Model):
    """「私も知りたい」"""

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="interests")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chie_interests")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "私も知りたい"
        verbose_name_plural = "私も知りたい"
        constraints = [models.UniqueConstraint(fields=["question", "user"], name="chie_interest_once")]


class Thanks(models.Model):
    """答えへの「参考になった」"""

    answer = models.ForeignKey(Answer, on_delete=models.CASCADE, related_name="thanks")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chie_thanks")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "参考になった"
        verbose_name_plural = "参考になった"
        constraints = [models.UniqueConstraint(fields=["answer", "user"], name="chie_thanks_once")]


class SurveyImport(models.Model):
    """
    事前アンケートから取り込んだ行の記録。
    掲示板で消した質問・答えが、次の取り込みでまた出てこないように残す。
    """

    kind = models.CharField(max_length=10)  # question / answer
    source_id = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "アンケートの取り込み記録"
        verbose_name_plural = "アンケートの取り込み記録"
        constraints = [models.UniqueConstraint(fields=["kind", "source_id"], name="chie_survey_import_once")]


class Genre(models.TextChoices):
    KIDS = "kids", "子ども・育児"
    BOOKS = "books", "本・マンガ"
    FURNITURE = "furniture", "家具・インテリア"
    APPLIANCE = "appliance", "家電"
    KITCHEN = "kitchen", "キッチン・食器"
    CLOTHES = "clothes", "服・靴"
    SPORTS = "sports", "スポーツ・アウトドア"
    FOOD = "food", "食べもの"
    OTHER = "other", "その他"


class Item(models.Model):
    """ゆずりあい: ゆずります・ください・貸します・借りたい (どれも無料)"""

    class Kind(models.TextChoices):
        GIVE = "give", "ゆずります"
        WANT = "want", "ください"
        LEND = "lend", "貸します"
        BORROW = "borrow", "借りたい"

    class State(models.TextChoices):
        OPEN = "open", "受付中"
        RESERVED = "reserved", "相手が決まりました"
        DONE = "done", "おわり"

    kind = models.CharField("種類", max_length=10, choices=Kind.choices)
    genre = models.CharField("ジャンル", max_length=20, choices=Genre.choices, default=Genre.OTHER)
    title = models.CharField("品物", max_length=80)
    body = models.TextField("説明", blank=True)
    photo_url = models.URLField("写真", max_length=500, blank=True)
    region = models.CharField("地域", max_length=30, choices=BOARD_REGION_CHOICES, blank=True)
    place = models.CharField("受け渡しの場所", max_length=80, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="出した人", on_delete=models.CASCADE, related_name="chie_items")
    nickname = models.CharField("ニックネーム", max_length=30, blank=True)
    state = models.CharField("状態", max_length=10, choices=State.choices, default=State.OPEN, db_index=True)
    status = models.CharField("ステータス", max_length=20, choices=Status.choices, default=Status.PUBLISHED, db_index=True)
    created_at = models.DateTimeField("作成日時", default=timezone.now, db_index=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        verbose_name = "ゆずりあい"
        verbose_name_plural = "ゆずりあい"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_kind_display()}: {self.title}"

    @property
    def display_name(self):
        return self.nickname or "名無しさん"

    @property
    def is_offer(self):
        """出す側 (ゆずります・貸します) か、探す側 (ください・借りたい) か"""
        return self.kind in (self.Kind.GIVE, self.Kind.LEND)

    @property
    def request_word(self):
        """見た人が押すボタンの言葉"""
        return {
            self.Kind.GIVE: "ほしい",
            self.Kind.WANT: "ゆずれます",
            self.Kind.LEND: "借りたい",
            self.Kind.BORROW: "貸せます",
        }[self.kind]

    @property
    def deal_word(self):
        """出した人が相手を決めるときの言葉"""
        return {
            self.Kind.GIVE: "ゆずる",
            self.Kind.WANT: "ゆずってもらう",
            self.Kind.LEND: "貸す",
            self.Kind.BORROW: "借りる",
        }[self.kind]

    def state_label(self):
        if self.state == self.State.DONE:
            return "おわり"
        if self.kind == self.Kind.LEND:
            return "貸し出しできます" if self.state == self.State.OPEN else "貸し出し中"
        if not self.is_offer:
            return "さがしています" if self.state == self.State.OPEN else "見つかりました"
        return self.get_state_display()


class Notice(models.Model):
    """募集・告知。1人1件まで、30日で自動で終わる。"""

    class Kind(models.TextChoices):
        SHOP = "shop", "お店・サービス"
        LESSON = "lesson", "教室・レッスン"
        EVENT = "event", "イベント・集まり"
        FRIENDS = "friends", "仲間・サークル"
        SITTER_FIND = "sitter_find", "シッターを探しています"
        SITTER_OFFER = "sitter_offer", "シッターできます"
        OTHER = "other", "その他"

    PR_KINDS = ("shop", "lesson")
    SITTER_KINDS = ("sitter_find", "sitter_offer")
    DAYS = 30

    kind = models.CharField("種類", max_length=20, choices=Kind.choices)
    title = models.CharField("タイトル", max_length=80)
    body = models.TextField("内容")
    region = models.CharField("地域", max_length=30, choices=BOARD_REGION_CHOICES, blank=True)
    place = models.CharField("場所", max_length=80, blank=True)
    event_date = models.DateField("日にち", null=True, blank=True)
    link = models.URLField("リンク", max_length=500, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="出した人", on_delete=models.CASCADE, related_name="chie_notices")
    nickname = models.CharField("ニックネーム", max_length=30, blank=True)
    status = models.CharField("ステータス", max_length=20, choices=Status.choices, default=Status.PUBLISHED, db_index=True)
    expires_at = models.DateTimeField("掲載の終わり", db_index=True)
    created_at = models.DateTimeField("作成日時", default=timezone.now, db_index=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        verbose_name = "募集・告知"
        verbose_name_plural = "募集・告知"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_kind_display()}: {self.title}"

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = (self.created_at or timezone.now()) + timedelta(days=self.DAYS)
        super().save(*args, **kwargs)

    @property
    def display_name(self):
        return self.nickname or "名無しさん"

    @property
    def is_pr(self):
        return self.kind in self.PR_KINDS

    @property
    def is_sitter(self):
        return self.kind in self.SITTER_KINDS

    @property
    def is_active(self):
        return self.status == Status.PUBLISHED and self.expires_at > timezone.now()

    @property
    def days_left(self):
        return max(0, (self.expires_at - timezone.now()).days)


class BoardProfile(models.Model):
    """掲示板のプロフィール (住んでいる地域・ひとこと)。ニックネームは Yapp 共通。"""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chie_profile")
    region = models.CharField("住んでいる地域", max_length=30, choices=BOARD_REGION_CHOICES, blank=True)
    intro = models.CharField("ひとこと", max_length=160, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "プロフィール"
        verbose_name_plural = "プロフィール"

    def __str__(self):
        return str(self.user)


class Notification(models.Model):
    """右上の🔔に出るお知らせ"""

    class Kind(models.TextChoices):
        ANSWER = "answer", "答え"
        REPLY = "reply", "返信"
        TALK = "talk", "やりとり"
        CHOSEN = "chosen", "相手に決まった"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chie_notifications")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    text = models.CharField(max_length=200)
    url = models.CharField(max_length=300)
    actor = models.CharField(max_length=30, blank=True)
    read_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "お知らせ"
        verbose_name_plural = "お知らせ"
        ordering = ["-created_at"]


class ItemRequest(models.Model):
    """
    品物への「ほしい」「借りたい」など、または告知への問い合わせ。
    出した人と送った人の2人だけのやりとりになる。item か notice のどちらか。
    """

    item = models.ForeignKey(Item, verbose_name="品物", on_delete=models.CASCADE, related_name="requests", null=True, blank=True)
    notice = models.ForeignKey(Notice, verbose_name="告知", on_delete=models.CASCADE, related_name="requests", null=True, blank=True)
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="送った人", on_delete=models.CASCADE, related_name="chie_requests")
    nickname = models.CharField("ニックネーム", max_length=30, blank=True)
    is_chosen = models.BooleanField("相手に決まった", default=False)
    owner_read_at = models.DateTimeField(null=True, blank=True)
    requester_read_at = models.DateTimeField(null=True, blank=True)
    last_message_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)

    class Meta:
        verbose_name = "やりとり"
        verbose_name_plural = "やりとり"
        ordering = ["-last_message_at"]
        constraints = [
            models.UniqueConstraint(fields=["item", "requester"], name="chie_request_once"),
            models.UniqueConstraint(fields=["notice", "requester"], name="chie_notice_request_once"),
        ]

    def __str__(self):
        return f"{self.subject.title} ← {self.display_name}"

    @property
    def subject(self):
        return self.item if self.item_id else self.notice

    @property
    def owner_id(self):
        return self.subject.owner_id

    @property
    def display_name(self):
        return self.nickname or "名無しさん"

    def is_member(self, user):
        return user.is_authenticated and user.pk in (self.requester_id, self.owner_id)

    def other_name(self, user):
        return self.subject.display_name if user.pk == self.requester_id else self.display_name

    def unread_for(self, user):
        read_at = self.requester_read_at if user.pk == self.requester_id else self.owner_read_at
        return read_at is None or read_at < self.last_message_at


class Message(models.Model):

    request = models.ForeignKey(ItemRequest, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chie_messages")
    body = models.TextField("メッセージ")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "メッセージ"
        verbose_name_plural = "メッセージ"
        ordering = ["created_at"]


class Report(models.Model):
    """通報 (質問・答え・品物)。運営が管理画面で見る。"""

    target = models.CharField("対象", max_length=20)  # question / answer / item / post / notice
    target_id = models.PositiveIntegerField("対象ID")
    reason = models.TextField("理由", blank=True)
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="通報した人", on_delete=models.SET_NULL, null=True, blank=True)
    handled = models.BooleanField("対応済み", default=False)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)

    class Meta:
        verbose_name = "通報"
        verbose_name_plural = "通報"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.target} #{self.target_id}"


class Post(models.Model):
    """つぶやき。テーマと地域のタグを付けると、あとから検索で見つかる。"""

    body = models.TextField("つぶやき")
    theme = models.CharField("テーマ", max_length=20, choices=THEME_CHOICES, blank=True)
    region = models.CharField("地域", max_length=30, choices=BOARD_REGION_CHOICES, blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="投稿者", on_delete=models.CASCADE, related_name="chie_posts")
    nickname = models.CharField("ニックネーム", max_length=30, blank=True)
    status = models.CharField("ステータス", max_length=20, choices=Status.choices, default=Status.PUBLISHED, db_index=True)
    created_at = models.DateTimeField("作成日時", default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "つぶやき"
        verbose_name_plural = "つぶやき"
        ordering = ["-created_at"]

    def __str__(self):
        return self.body[:40]

    @property
    def display_name(self):
        return self.nickname or "名無しさん"


class PostReply(models.Model):

    post = models.ForeignKey(Post, verbose_name="つぶやき", on_delete=models.CASCADE, related_name="replies")
    body = models.TextField("返信")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="投稿者", on_delete=models.CASCADE, related_name="chie_post_replies")
    nickname = models.CharField("ニックネーム", max_length=30, blank=True)
    status = models.CharField("ステータス", max_length=20, choices=Status.choices, default=Status.PUBLISHED, db_index=True)
    created_at = models.DateTimeField("作成日時", default=timezone.now)

    class Meta:
        verbose_name = "つぶやきへの返信"
        verbose_name_plural = "つぶやきへの返信"
        ordering = ["created_at"]

    def __str__(self):
        return self.body[:40]

    @property
    def display_name(self):
        return self.nickname or "名無しさん"


class PostLike(models.Model):
    """つぶやきへの「役に立った」"""

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chie_post_likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "役に立った (つぶやき)"
        verbose_name_plural = "役に立った (つぶやき)"
        constraints = [models.UniqueConstraint(fields=["post", "user"], name="chie_post_like_once")]
