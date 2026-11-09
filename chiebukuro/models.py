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
    SEASON_CHOICES = [
        ("auto", "自動（時期に合わせる）"),
        ("none", "いつものデザイン"),
        ("spring", "春（桜）"),
        ("nationalday", "スイス建国記念日（8月1日）"),
        ("halloween", "ハロウィン"),
        ("autumn", "秋（紅葉）"),
        ("christmas", "クリスマス"),
        ("newyear", "お正月"),
    ]
    hero_season = models.CharField(
        "HOME上部の季節のデザイン",
        max_length=20,
        choices=SEASON_CHOICES,
        default="auto",
        help_text="自動: 春 4/1〜4/25、建国記念日 7/25〜8/1、ハロウィン 10/18〜10/31、秋 11月、クリスマス 12/1〜12/26、お正月 12/30〜1/7",
    )
    preview_key = models.CharField(
        "先行公開のリンクの鍵",
        max_length=40,
        blank=True,
        help_text="公開前でも、この鍵つきのリンクを開いた人は掲示板を見られます。管理画面のボタンで作り直すと、古いリンクは使えなくなります。",
    )
    rules_updated_at = models.DateTimeField(
        "ルールを更新した日時",
        null=True,
        blank=True,
        help_text="ルールを変えたら、ここを「今日」「現在」にして保存してください。これより前に同意した人には、次に書きこむときにもう一度同意の画面が出ます。",
    )
    release_start = models.DateField(
        "小出しを始めた日",
        null=True,
        blank=True,
        help_text="アンケートから取り込んだ質問を、この日から毎日少しずつ公開します。「公開する」をオンにした日が自動で入ります。",
    )
    release_first = models.PositiveIntegerField(
        "最初に出すアンケートの質問の数",
        default=30,
        help_text="公開の日 (と、公開前の先行リンク) に見せる、アンケートから取り込んだ質問の数",
    )
    release_per_day = models.PositiveIntegerField(
        "毎日ふやす質問の数",
        default=3,
        help_text="小出しを始めた日の翌日から、毎朝この数だけ、公開待ちの質問を公開します (答えもいっしょに)。0 なら止まります。",
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

    def save(self, *args, **kwargs):
        # 公開した日から、アンケートの質問の小出しを始める
        if self.is_open and not self.release_start:
            self.release_start = timezone.localdate()
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = list(kwargs["update_fields"]) + ["release_start"]
        super().save(*args, **kwargs)

    def released_target(self, today=None):
        """今日までに見せてよい、アンケートから取り込んだ質問の数"""

        today = today or timezone.localdate()
        days = (today - self.release_start).days if self.release_start else 0
        return self.release_first + self.release_per_day * max(0, days)

    def new_preview_key(self):
        import secrets

        self.preview_key = secrets.token_urlsafe(12)
        self.save(update_fields=["preview_key", "updated_at"])
        return self.preview_key

    def season(self, today):
        """HOME上部に使う季節のデザイン ("" ならいつもの)"""

        if self.hero_season == "none":
            return ""
        if self.hero_season != "auto":
            return self.hero_season
        month, day = today.month, today.day
        if month == 4 and day <= 25:
            return "spring"
        if (month == 7 and day >= 25) or (month == 8 and day == 1):
            return "nationalday"
        if month == 10 and day >= 18:
            return "halloween"
        if month == 11:
            return "autumn"
        if month == 12 and day <= 26:
            return "christmas"
        if (month == 12 and day >= 30) or (month == 1 and day <= 7):
            return "newyear"
        return ""


class Status(models.TextChoices):
    PUBLISHED = "published", "公開"
    HIDDEN = "hidden", "非公開"


# アンケートから取り込んだ質問は「公開待ち」から少しずつ公開する (質問だけの状態)
QUEUED = "queued"
QUESTION_STATUS_CHOICES = Status.choices + [(QUEUED, "公開待ち（アンケートから小出し）")]


class Question(models.Model):

    class Source(models.TextChoices):
        MEMBER = "member", "利用者"
        STAFF = "staff", "運営"
        SURVEY = "survey", "事前アンケート"

    body = models.TextField("質問")
    photo_url = models.URLField("写真", max_length=500, blank=True)
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
    status = models.CharField("ステータス", max_length=20, choices=QUESTION_STATUS_CHOICES, default=Status.PUBLISHED, db_index=True)
    # 公開待ちの順番 (小さいものから公開する)
    release_rank = models.PositiveIntegerField("公開の順番", null=True, blank=True, help_text="公開待ちの質問は、小さい数から順に公開されます。")
    # アンケートで押された「私も知りたい」(取り込み時の数。掲示板で押された分は Interest)
    survey_interest_count = models.PositiveIntegerField("アンケートでの「知りたい」", default=0)
    # 事前アンケートの質問 (取り込み元)
    survey_question_id = models.PositiveIntegerField("アンケートの質問ID", null=True, blank=True, unique=True)
    home_pick = models.BooleanField("HOMEの注目に出す", default=False, help_text="オンにすると、HOMEの「今週の注目」に先に出ます。")
    # 新しい答えがついた日時 (HOME の「新しい答え順」)
    last_answered_at = models.DateTimeField("最後の答え", null=True, blank=True, db_index=True)
    edited_at = models.DateTimeField("編集した日時", null=True, blank=True)
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
    photo_url = models.URLField("写真", max_length=500, blank=True)
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
    home_pick = models.BooleanField("HOMEの注目に出す", default=False, help_text="オンにすると、HOMEの「今週の注目」に先に出ます。")
    status = models.CharField("ステータス", max_length=20, choices=Status.choices, default=Status.PUBLISHED, db_index=True)
    edited_at = models.DateTimeField("編集した日時", null=True, blank=True)
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
    photo_url = models.URLField("写真", max_length=500, blank=True)
    region = models.CharField("地域", max_length=30, choices=BOARD_REGION_CHOICES, blank=True)
    place = models.CharField("場所", max_length=80, blank=True)
    event_date = models.DateField("日にち", null=True, blank=True)
    link = models.URLField("リンク", max_length=500, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="出した人", on_delete=models.CASCADE, related_name="chie_notices")
    nickname = models.CharField("ニックネーム", max_length=30, blank=True)
    status = models.CharField("ステータス", max_length=20, choices=Status.choices, default=Status.PUBLISHED, db_index=True)
    expires_at = models.DateTimeField("掲載の終わり", db_index=True)
    is_sample = models.BooleanField("テスト用（架空）", default=False, help_text="先行テスト用の架空の告知。「テスト用・架空」の印が付きます。公開前に管理画面からまとめて消してください。")
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

    class AvatarKind(models.TextChoices):
        LETTER = "letter", "名前の1文字"
        ILLUST = "illust", "イラスト"
        PHOTO = "photo", "写真"

    avatar_kind = models.CharField("アイコン", max_length=10, choices=AvatarKind.choices, default=AvatarKind.LETTER)
    avatar_parts = models.JSONField("イラストの組み合わせ", default=dict, blank=True)
    photo_url = models.URLField("プロフィール写真", max_length=500, blank=True)
    rules_agreed_at = models.DateTimeField("ルールに同意した日時", null=True, blank=True)

    class PushFrequency(models.TextChoices):
        INSTANT = "instant", "すぐに知らせる"
        DAILY = "daily", "1日1回まとめて（夜7時）"
        OFF = "off", "プッシュ通知はしない"

    push_frequency = models.CharField("プッシュ通知の頻度", max_length=10, choices=PushFrequency.choices, default=PushFrequency.INSTANT)
    push_answer = models.BooleanField("自分の質問・知りたい質問に答えがついたとき", default=True)
    push_reply = models.BooleanField("つぶやきに返信があったとき", default=True)
    push_stamp = models.BooleanField("スタンプが押されたとき", default=False)
    push_talk = models.BooleanField("2人だけのやりとりにメッセージが来たとき", default=True)
    daily_popup = models.BooleanField("開いたときの「今日のひとこと」を出す", default=True)
    daily_charm = models.BooleanField("今日のひとこと: お守り占い", default=True)
    daily_word = models.BooleanField("今日のひとこと: スイスドイツ語", default=True)
    daily_trivia = models.BooleanField("今日のひとこと: 豆知識", default=True)
    daily_poll = models.BooleanField("今日のひとこと: アンケート", default=True)

    class Color(models.TextChoices):
        CLASSIC = "classic", "スイスレッド"
        SAKURA = "sakura", "さくら"
        MINT = "mint", "ミント"
        LAKE = "lake", "レマン湖"
        LAVENDER = "lavender", "ラベンダー"
        LEMON = "lemon", "レモン"

    color = models.CharField("着せかえの色", max_length=20, choices=Color.choices, default=Color.CLASSIC)
    color_auto = models.BooleanField("12時間ごとに色を変える", default=False)
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
        STAMP = "stamp", "スタンプ"

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


class Contact(models.Model):
    """運営へのお問い合わせ (広告・掲示板について・そのほか)。管理画面で見る。"""

    class Kind(models.TextChoices):
        AD = "ad", "広告を出したい"
        BOARD = "board", "掲示板について（不具合・ご要望）"
        OTHER = "other", "そのほか"

    kind = models.CharField("種類", max_length=20, choices=Kind.choices, default=Kind.BOARD)
    message = models.TextField("内容")
    email = models.EmailField("返信先メール", blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="送った人", on_delete=models.SET_NULL, null=True, blank=True)
    handled = models.BooleanField("対応済み", default=False)
    created_at = models.DateTimeField("送った日時", auto_now_add=True)

    class Meta:
        verbose_name = "お問い合わせ"
        verbose_name_plural = "お問い合わせ"
        ordering = ["-created_at"]

    def __str__(self):
        return self.message[:40]


class Report(models.Model):
    """通報 (質問・答え・品物)。運営が管理画面で見る。"""

    target = models.CharField("対象", max_length=20)  # question / answer / item / post / reply / notice
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
    home_pick = models.BooleanField("HOMEの注目に出す", default=False, help_text="オンにすると、HOMEの「今週の注目」に先に出ます。")
    photo_url = models.URLField("写真", max_length=500, blank=True)
    theme = models.CharField("テーマ", max_length=20, choices=THEME_CHOICES, blank=True)
    region = models.CharField("地域", max_length=30, choices=BOARD_REGION_CHOICES, blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="投稿者", on_delete=models.CASCADE, related_name="chie_posts")
    nickname = models.CharField("ニックネーム", max_length=30, blank=True)
    status = models.CharField("ステータス", max_length=20, choices=Status.choices, default=Status.PUBLISHED, db_index=True)
    edited_at = models.DateTimeField("編集した日時", null=True, blank=True)
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
    photo_url = models.URLField("写真", max_length=500, blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="投稿者", on_delete=models.CASCADE, related_name="chie_post_replies")
    nickname = models.CharField("ニックネーム", max_length=30, blank=True)
    status = models.CharField("ステータス", max_length=20, choices=Status.choices, default=Status.PUBLISHED, db_index=True)
    edited_at = models.DateTimeField("編集した日時", null=True, blank=True)
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


# スタンプ (つぶやき・返信・回答に押せる)。key は変えない (データに残るため)
STAMPS = [
    ("helpful", "💡", "役に立った"),
    ("like", "👍", "いいね"),
    ("thanks", "🙏", "ありがとう"),
    ("agree", "🤝", "わかる"),
    ("laugh", "😂", "笑った"),
    ("cheer", "📣", "応援してる"),
]
STAMP_CHOICES = [(key, f"{emoji} {label}") for key, emoji, label in STAMPS]


class Reaction(models.Model):
    """スタンプ。1人が同じものに同じスタンプを押せるのは1回 (違うスタンプは複数OK)"""

    class Target(models.TextChoices):
        POST = "post", "つぶやき"
        REPLY = "reply", "返信"
        ANSWER = "answer", "回答"

    target = models.CharField(max_length=10, choices=Target.choices)
    target_id = models.PositiveIntegerField()
    stamp = models.CharField(max_length=20, choices=STAMP_CHOICES)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chie_reactions")
    target_author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="chie_reactions_received"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "スタンプ"
        verbose_name_plural = "スタンプ"
        indexes = [models.Index(fields=["target", "target_id"])]
        constraints = [
            models.UniqueConstraint(fields=["target", "target_id", "user", "stamp"], name="chie_reaction_once"),
        ]


class Poll(models.Model):
    """HOME の「みんなのアンケート」(運営が管理画面で作る)"""

    question = models.CharField("質問", max_length=120)
    is_active = models.BooleanField("HOME に出す", default=True)
    created_at = models.DateTimeField("作成日時", default=timezone.now)

    class Meta:
        verbose_name = "アンケート"
        verbose_name_plural = "アンケート"
        ordering = ["-created_at"]

    def __str__(self):
        return self.question


class PollChoice(models.Model):

    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="choices")
    label = models.CharField("選択肢", max_length=60)
    order = models.PositiveSmallIntegerField("並び順", default=0)

    class Meta:
        verbose_name = "選択肢"
        verbose_name_plural = "選択肢"
        ordering = ["order", "pk"]

    def __str__(self):
        return self.label


class PollVote(models.Model):
    """1つのアンケートに1票。ログインしていない人はブラウザごと (cookie)"""

    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="votes")
    choice = models.ForeignKey(PollChoice, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    voter_key = models.CharField(max_length=40, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "アンケートの票"
        verbose_name_plural = "アンケートの票"


class Sponsor(models.Model):
    """HOME の広告枠 (運営が管理画面で入れる)。期間中のものから1つ出す"""

    name = models.CharField("広告主", max_length=80)
    title = models.CharField("見出し", max_length=80)
    text = models.CharField("ひとこと", max_length=160, blank=True)
    link = models.URLField("リンク先", max_length=500)
    image_url = models.URLField("画像のURL", max_length=500, blank=True)
    starts_on = models.DateField("開始日", default=timezone.localdate)
    ends_on = models.DateField("終了日", null=True, blank=True)
    is_active = models.BooleanField("出す", default=True)
    clicks = models.PositiveIntegerField("クリック数", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "広告枠"
        verbose_name_plural = "広告枠"
        ordering = ["-starts_on"]

    def __str__(self):
        return f"{self.name}: {self.title}"


class PushDevice(models.Model):
    """プッシュ通知を受け取る端末 (Service Worker と鍵は Swiss News・和食と共通)"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chie_push_devices")
    endpoint = models.TextField(unique=True)
    p256dh = models.TextField()
    auth = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "プッシュ通知の端末"
        verbose_name_plural = "プッシュ通知の端末"
