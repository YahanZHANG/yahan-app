from django.conf import settings
from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
)
from django.db import models
from django.urls import reverse
from django.utils import timezone


# =========================================================
# 食材と買える店
# =========================================================

class ShopType(models.Model):
    """
    食材を買える店の種類。
    rank が小さいほど身近な店 (1 = 普通のスーパー)。
    """

    code = models.SlugField(
        "コード",
        max_length=30,
        unique=True,
    )

    name = models.CharField(
        "店の種類",
        max_length=50,
    )

    description = models.CharField(
        "説明",
        max_length=200,
        blank=True,
        help_text="例: Migros・Coop・Denner・Aldi・Lidl など",
    )

    rank = models.PositiveSmallIntegerField(
        "身近さ",
        unique=True,
        help_text="1 が最も身近。レシピの「どこまで行けば作れるか」に使う。",
    )

    class Meta:
        verbose_name = "店の種類"
        verbose_name_plural = "店の種類"
        ordering = ["rank"]

    def __str__(self):
        return self.name


class Ingredient(models.Model):
    """
    食材。調味料も食材として登録する。
    """

    CATEGORY_CHOICES = [
        ("meat", "肉"),
        ("fish", "魚介"),
        ("vegetable", "野菜"),
        ("fruit", "果物"),
        ("egg", "卵"),
        ("dairy", "乳製品"),
        ("soy", "豆・大豆製品"),
        ("grain", "米・麺・粉"),
        ("mushroom", "きのこ"),
        ("seaweed", "海藻・乾物"),
        ("seasoning", "調味料"),
        ("other", "その他"),
    ]

    name = models.CharField(
        "食材名",
        max_length=100,
        unique=True,
    )

    name_de = models.CharField(
        "ドイツ語名",
        max_length=100,
        blank=True,
    )

    name_fr = models.CharField(
        "フランス語名",
        max_length=100,
        blank=True,
    )

    category = models.CharField(
        "カテゴリー",
        max_length=20,
        choices=CATEGORY_CHOICES,
        default="other",
    )

    search_group = models.CharField(
        "食材検索グループ",
        max_length=100,
        blank=True,
        db_index=True,
        help_text="例: 鶏もも肉→鶏肉。空欄の場合は食材名と同じ扱い。",
    )

    photo_url = models.URLField(
        "写真",
        max_length=500,
        blank=True,
        help_text="下の「写真をアップロード」か、Wikimedia Commons の画像 URL。",
    )

    photo_credit = models.CharField(
        "写真の出典",
        max_length=300,
        blank=True,
        help_text="Wikimedia の写真は作者とライセンスを必ず残す。",
    )

    photo_source = models.URLField(
        "写真の元ページ",
        max_length=500,
        blank=True,
    )

    photo_auto_tried = models.BooleanField(
        "写真を自動で探した",
        default=False,
        help_text="自動で一度探した食材は、写真を外しても探し直さない。",
    )

    shops = models.ManyToManyField(
        ShopType,
        verbose_name="買える店",
        blank=True,
        related_name="ingredients",
    )

    buying_notes = models.TextField(
        "買い方のメモ",
        blank=True,
        help_text="例: Coop の肉売り場で「Fondue Chinoise」用を買うと薄切り肉になる。",
    )

    created_at = models.DateTimeField(
        "登録日時",
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        "更新日時",
        auto_now=True,
    )

    class Meta:
        verbose_name = "食材"
        verbose_name_plural = "食材"
        ordering = ["category", "name"]

    def __str__(self):
        return self.name

    @property
    def group_name(self):
        return self.search_group or self.name

    def easiest_shop_rank(self):
        """
        一番身近に買える店の rank。店が未登録なら None。
        """

        ranks = [shop.rank for shop in self.shops.all()]

        return min(ranks) if ranks else None


class Substitute(models.Model):
    """
    日本の食材 → スイスで代わりに使える食材。
    例: 大根 → Rettich

    会員も投稿できる。食材リストにないものは substitute_name に書き、
    管理者が確認して公開する (必要なら食材を登録してつなぐ)。
    """

    STATUS_CHOICES = [
        ("draft", "確認待ち"),
        ("published", "公開"),
    ]

    original_name = models.CharField(
        "日本の食材",
        max_length=100,
        db_index=True,
    )

    substitute = models.ForeignKey(
        Ingredient,
        verbose_name="スイスでの代用品",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="substitutes_for",
    )

    substitute_name = models.CharField(
        "スイスでの代用品（食材リストにないとき）",
        max_length=100,
        blank=True,
        help_text="例: Kohlrabi。上の「スイスでの代用品」を選んだときは空欄でよい。",
    )

    tips = models.TextField(
        "使うときのコツ",
        blank=True,
        help_text="例: 少し辛いので下茹でを長めに。",
    )

    status = models.CharField(
        "公開状態",
        max_length=20,
        choices=STATUS_CHOICES,
        default="published",
        db_index=True,
    )

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="投稿した会員",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="washoku_substitutes",
    )

    created_at = models.DateTimeField(
        "登録日時",
        auto_now_add=True,
        null=True,
    )

    class Meta:
        verbose_name = "代わりの食材"
        verbose_name_plural = "代わりの食材"
        ordering = ["original_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["original_name", "substitute"],
                name="washoku_unique_substitute",
            )
        ]

    def __str__(self):
        return f"{self.original_name} → {self.display_name}"

    @property
    def display_name(self):
        return self.substitute.name if self.substitute_id else self.substitute_name


# =========================================================
# レシピ
# =========================================================

class MoodTag(models.Model):
    """
    「今日はどんな気分？」で使うタグ。
    """

    name = models.CharField(
        "気分",
        max_length=50,
        unique=True,
    )

    display_order = models.PositiveIntegerField(
        "表示順",
        default=0,
    )

    class Meta:
        verbose_name = "気分タグ"
        verbose_name_plural = "気分タグ"
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


class Recipe(models.Model):

    CATEGORY_CHOICES = [
        ("meat", "肉のおかず"),
        ("fish", "魚のおかず"),
        ("rice", "丼・ご飯もの"),
        ("noodle", "麺"),
        ("side", "副菜"),
        ("soup", "汁物・鍋"),
        ("flour", "粉もの"),
        ("sweets", "デザート・おやつ"),
        ("bread", "パン"),
        ("apero", "アペロ・持ち寄り"),
        ("yoshoku", "和風洋食"),
        ("chinese", "中華"),
        ("korean", "韓国"),
        ("vietnamese", "ベトナム"),
        ("thai", "タイ"),
        ("europe", "本場の洋食"),
        ("other", "その他"),
    ]

    STATUS_CHOICES = [
        ("draft", "下書き"),
        ("published", "公開"),
    ]

    ORIGIN_CHOICES = [
        ("ai", "AI下書き"),
        ("manual", "手書き"),
        ("member", "会員の投稿"),
    ]

    name = models.CharField(
        "料理名",
        max_length=200,
        unique=True,
    )

    description = models.CharField(
        "ひとこと紹介",
        max_length=200,
        blank=True,
    )

    category = models.CharField(
        "料理カテゴリー",
        max_length=20,
        choices=CATEGORY_CHOICES,
        default="other",
    )

    cooking_time_minutes = models.PositiveIntegerField(
        "調理時間（分）",
        null=True,
        blank=True,
    )

    servings = models.PositiveSmallIntegerField(
        "何人分",
        null=True,
        blank=True,
    )

    # 載せる写真は1枚。会員が投稿した写真 (MemberPhoto) の中から、最初の1枚か管理者が選んだもの
    photo_1 = models.URLField("載せる写真", max_length=500, blank=True)

    serving_unit = models.CharField(
        "数え方",
        max_length=10,
        blank=True,
        help_text="パンやおやつなど、人数でなく数で数えるとき（例: 個、切れ）。空欄なら「人分」。栄養はこの1つ分。",
    )

    steps = models.TextField(
        "作り方",
        help_text="1行に1手順。",
    )

    swiss_tips = models.TextField(
        "スイスで作るときのコツ",
        blank=True,
    )

    ingredients = models.ManyToManyField(
        Ingredient,
        through="RecipeIngredient",
        related_name="recipes",
    )

    mood_tags = models.ManyToManyField(
        MoodTag,
        verbose_name="気分タグ",
        blank=True,
        related_name="recipes",
    )

    # 1人分の栄養の目安 (材料からの概算)
    energy_kcal = models.PositiveIntegerField(
        "エネルギー（kcal）",
        null=True,
        blank=True,
        help_text="1人分の目安。",
    )

    protein_g = models.DecimalField(
        "たんぱく質（g）",
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
    )

    fat_g = models.DecimalField(
        "脂質（g）",
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
    )

    carbs_g = models.DecimalField(
        "炭水化物（g）",
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
    )

    salt_g = models.DecimalField(
        "食塩相当量（g）",
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
    )

    shop_rank = models.PositiveSmallIntegerField(
        "必要な店",
        null=True,
        blank=True,
        editable=False,
        db_index=True,
        help_text=(
            "必須の材料をそろえるのに、どの店まで行く必要があるか (ShopType.rank)。"
            "材料から自動で計算する。"
        ),
    )

    status = models.CharField(
        "公開状態",
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
        db_index=True,
    )

    origin = models.CharField(
        "作成元",
        max_length=20,
        choices=ORIGIN_CHOICES,
        default="manual",
    )

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="投稿した会員",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="washoku_submitted_recipes",
    )

    submitted_ingredients = models.TextField(
        "投稿された材料（原文）",
        blank=True,
        help_text=(
            "会員が書いた材料のメモ。食材リストにない材料は自動でつながらないので、"
            "必要なら食材を登録してから下の「材料」に追加する。"
        ),
    )

    created_at = models.DateTimeField(
        "登録日時",
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        "更新日時",
        auto_now=True,
    )

    class Meta:
        verbose_name = "レシピ"
        verbose_name_plural = "レシピ"
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def servings_label(self):
        """例: 4人分、8切れ分"""
        return f"{self.servings}{self.serving_unit or '人'}分"

    @property
    def per_serving_label(self):
        """カード用の短い形。例: 1人分、1個"""
        return f"1{self.serving_unit}" if self.serving_unit else "1人分"

    @property
    def nutrition_label(self):
        """栄養の見出し。例: 1人分（1食分）、1切れあたり"""
        if self.serving_unit:
            return f"1{self.serving_unit}あたり"
        return "1人分（1食分）"

    @property
    def has_nutrition(self):
        return None not in (self.energy_kcal, self.protein_g, self.fat_g, self.carbs_g)

    def pfc_ratio(self):
        """
        エネルギーに占めるたんぱく質・脂質・炭水化物の割合 (%)。
        """

        if not self.has_nutrition:
            return None

        parts = [
            float(self.protein_g) * 4,
            float(self.fat_g) * 9,
            float(self.carbs_g) * 4,
        ]

        total = sum(parts)

        if not total:
            return None

        protein, fat = (round(part * 100 / total) for part in parts[:2])

        return {
            "protein": protein,
            "fat": fat,
            "carbs": 100 - protein - fat,
        }

    def step_list(self):
        return [
            line.strip()
            for line in self.steps.splitlines()
            if line.strip()
        ]

    def compute_shop_rank(self):
        """
        必須の材料それぞれの「一番身近な店」のうち、最も遠いもの。
        店が未登録の材料があれば None (判定できない)。
        """

        ranks = []

        for item in self.recipe_ingredients.select_related(
            "ingredient"
        ).prefetch_related("ingredient__shops"):

            if item.is_optional:
                continue

            rank = item.ingredient.easiest_shop_rank()

            if rank is None:
                return None

            ranks.append(rank)

        return max(ranks) if ranks else None

    def update_shop_rank(self):

        self.shop_rank = self.compute_shop_rank()

        Recipe.objects.filter(pk=self.pk).update(
            shop_rank=self.shop_rank
        )


class RecipeIngredient(models.Model):

    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name="recipe_ingredients",
    )

    ingredient = models.ForeignKey(
        Ingredient,
        verbose_name="食材",
        on_delete=models.PROTECT,
        related_name="recipe_ingredients",
    )

    amount = models.CharField(
        "分量",
        max_length=100,
        blank=True,
    )

    is_seasoning = models.BooleanField(
        "調味料として扱う",
        default=False,
        help_text="ONにすると「家にある食材で選ぶ」の対象外になる。",
    )

    is_optional = models.BooleanField(
        "なくてもよい",
        default=False,
    )

    display_order = models.PositiveIntegerField(
        "表示順",
        default=0,
    )

    class Meta:
        verbose_name = "材料"
        verbose_name_plural = "材料"
        ordering = ["display_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["recipe", "ingredient"],
                name="washoku_unique_ingredient_per_recipe",
            )
        ]

    def __str__(self):
        return f"{self.recipe.name} - {self.ingredient.name}"


# =========================================================
# 家族と評価
# =========================================================

class Household(models.Model):

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="washoku_households_created",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "家族"
        verbose_name_plural = "家族"

    def __str__(self):

        if self.created_by:
            return f"{self.created_by.username}の家族"

        return f"家族 {self.pk}"


class HouseholdMember(models.Model):

    household = models.ForeignKey(
        Household,
        on_delete=models.CASCADE,
        related_name="members",
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="washoku_membership",
    )

    joined_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "家族メンバー"
        verbose_name_plural = "家族メンバー"

    def __str__(self):
        return self.user.username


class HouseholdInvite(models.Model):

    STATUS_CHOICES = [
        ("pending", "承認待ち"),
        ("accepted", "参加済み"),
        ("declined", "辞退"),
    ]

    household = models.ForeignKey(
        Household,
        on_delete=models.CASCADE,
        related_name="invites",
    )

    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="washoku_invites_sent",
    )

    invited_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="washoku_invites_received",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "家族への招待"
        verbose_name_plural = "家族への招待"

    def __str__(self):
        return f"{self.invited_by.username} → {self.invited_user.username}"


class RecipeRating(models.Model):
    """
    ユーザーごとの好み (1〜5)。家族の平均で並べ替えに使う。
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="washoku_ratings",
    )

    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name="ratings",
    )

    rating = models.PositiveSmallIntegerField(
        "評価",
        validators=[
            MinValueValidator(1),
            MaxValueValidator(5),
        ],
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "評価"
        verbose_name_plural = "評価"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "recipe"],
                name="washoku_unique_rating_per_user",
            )
        ]

    def __str__(self):
        return f"{self.user} - {self.recipe.name}: {self.rating}"


class RecipeFavorite(models.Model):
    """
    お気に入りに保存したレシピ (本人だけが見られる)。
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="washoku_favorites",
    )

    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name="favorites",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "お気に入り"
        verbose_name_plural = "お気に入り"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "recipe"],
                name="washoku_unique_favorite",
            )
        ]

    def __str__(self):
        return f"{self.user} - {self.recipe.name}"


class RecipeNote(models.Model):
    """
    レシピごとの自分だけのメモ。ほかの人 (家族も) には見えない。
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="washoku_notes",
    )

    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name="notes",
    )

    body = models.TextField(
        "メモ",
        max_length=2000,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "レシピのメモ"
        verbose_name_plural = "レシピのメモ"
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "recipe"],
                name="washoku_unique_note",
            )
        ]

    def __str__(self):
        return f"{self.user} - {self.recipe.name}"


# =========================================================
# お店
# =========================================================

class MemberPhoto(models.Model):
    """
    会員が投稿した料理・食材の写真。ページに載るのは1枚だけで、
    最初の1枚が自動で載り、2枚目からは管理者が選ぶ。
    """

    recipe = models.ForeignKey(
        Recipe,
        verbose_name="料理",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="member_photos",
    )

    ingredient = models.ForeignKey(
        Ingredient,
        verbose_name="食材",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="member_photos",
    )

    url = models.URLField(
        "写真",
        max_length=500,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="投稿した人",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="washoku_photos",
    )

    admin_checked = models.BooleanField(
        "確認済み",
        default=False,
        help_text="管理画面の「対応待ち」に出さないようにするための印。",
    )

    created_at = models.DateTimeField(
        "投稿日時",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "投稿された写真"
        verbose_name_plural = "投稿された写真"
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"{self.target} の写真"

    @property
    def target(self):
        return self.recipe or self.ingredient

    @property
    def target_field(self):
        """target で、載せる写真の URL を入れる項目"""
        return "photo_1" if self.recipe_id else "photo_url"

    @property
    def is_shown(self):
        return getattr(self.target, self.target_field) == self.url


class Store(models.Model):
    """
    アジア・日本食材のお店。みんなが口コミを書ける。
    """

    KIND_CHOICES = [
        ("japanese", "日韓食材店"),
        ("asian", "中華食材店"),
        ("southeast", "その他のアジア食材店"),
    ]

    name = models.CharField(
        "店名",
        max_length=100,
    )

    kind = models.CharField(
        "種類",
        max_length=20,
        choices=KIND_CHOICES,
    )

    city = models.CharField(
        "都市",
        max_length=50,
        default="Zürich",
    )

    area = models.CharField(
        "地区",
        max_length=50,
        blank=True,
        help_text="例: Oerlikon、Seefeld、中央駅",
    )

    address = models.CharField(
        "住所",
        max_length=200,
    )

    website = models.URLField(
        "ウェブサイト",
        blank=True,
    )

    opening_hours = models.CharField(
        "営業時間",
        max_length=200,
        blank=True,
    )

    photo_url = models.URLField(
        "写真",
        max_length=500,
        blank=True,
    )

    description = models.TextField(
        "紹介",
        blank=True,
    )

    has_online_shop = models.BooleanField(
        "ネット通販あり",
        default=False,
    )

    latitude = models.FloatField(
        "緯度",
        null=True,
        blank=True,
        help_text="空なら住所から自動で調べる。",
    )

    longitude = models.FloatField(
        "経度",
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(
        "表示する",
        default=True,
    )

    updated_at = models.DateTimeField(
        "更新日時",
        auto_now=True,
    )

    class Meta:
        verbose_name = "お店"
        verbose_name_plural = "お店"
        ordering = ["city", "kind", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "address"],
                name="washoku_unique_store",
            )
        ]

    def __str__(self):
        return f"{self.name}（{self.area or self.city}）"

    @property
    def map_url(self):
        from urllib.parse import quote_plus

        return (
            "https://www.google.com/maps/search/?api=1&query="
            + quote_plus(f"{self.name} {self.address}")
        )


class Feedback(models.Model):
    """
    「このアプリについて」の質問箱から届いたご意見・ご要望 (匿名)。
    """

    message = models.TextField(
        "ご意見・ご要望",
        max_length=1000,
    )

    is_read = models.BooleanField(
        "確認済み",
        default=False,
    )

    created_at = models.DateTimeField(
        "送信日時",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "ご意見"
        verbose_name_plural = "ご意見"
        ordering = ["-created_at"]

    def __str__(self):
        return self.message[:50]


# =========================================================
# みんなの投稿 (コラム・おすすめ商品)
# =========================================================

class Post(models.Model):
    """
    会員が書くコラム・体験談、スーパーで買えるおすすめ商品、外部サイトの参考リンク、
    管理者が作るアンケート (選択肢は PollChoice)。
    管理者が公開するまでは、書いた本人と管理者にだけ見える。
    参考リンクは、記事を写さずに要点だけを自分の言葉で書き、出典とリンクを載せる。
    """

    KIND_CHOICES = [
        ("column", "コラム"),
        ("product", "おすすめ商品"),
        ("link", "参考リンク"),
        ("poll", "アンケート"),
    ]

    STATUS_CHOICES = [
        ("draft", "確認待ち"),
        ("published", "公開"),
    ]

    SHOP_CHOICES = [
        ("migros", "Migros"),
        ("coop", "Coop"),
        ("denner", "Denner"),
        ("aldi", "Aldi"),
        ("lidl", "Lidl"),
        ("asian", "アジア・日系の店"),
        ("other", "その他"),
    ]

    SECTION_CHOICES = [
        ("frozen", "冷凍"),
        ("chilled", "冷蔵・チルド"),
        ("pantry", "常温"),
    ]

    kind = models.CharField(
        "種類",
        max_length=20,
        choices=KIND_CHOICES,
        db_index=True,
    )

    title = models.CharField(
        "タイトル・商品名",
        max_length=100,
    )

    # アンケートは本文なしでもよい (会員のフォームでは必須のまま)
    body = models.TextField(
        "本文",
        max_length=4000,
        blank=True,
    )

    # コラムの写真 (2枚まで)
    photo_1 = models.URLField("写真1", max_length=500, blank=True)
    photo_2 = models.URLField("写真2", max_length=500, blank=True)

    # 買えるお店は複数選べる。SHOP_CHOICES のコードをカンマでつなげて入れる (例: "migros,coop")
    shop = models.CharField(
        "買えるお店",
        max_length=200,
        blank=True,
        help_text="SHOP_CHOICES のコードをカンマ区切りで (例: migros,coop)",
    )

    section = models.CharField(
        "売り場",
        max_length=20,
        choices=SECTION_CHOICES,
        blank=True,
    )

    resembles = models.CharField(
        "日本の何に近い？",
        max_length=100,
        blank=True,
        help_text="例: 冷凍餃子、ちくわ",
    )

    url = models.URLField(
        "記事のURL",
        max_length=500,
        blank=True,
    )

    source = models.CharField(
        "出典",
        max_length=200,
        blank=True,
        help_text="サイト名・書いた人・公開日など",
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="投稿した会員",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="washoku_posts",
    )

    status = models.CharField(
        "公開状態",
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
        db_index=True,
    )

    ingredients = models.ManyToManyField(
        Ingredient,
        verbose_name="関係する食材",
        blank=True,
        related_name="posts",
        help_text="選んだ食材（と同じ検索グループの食材）を使うレシピや食材のページに、この投稿が「関連する読みもの」として出ます。",
    )

    is_featured = models.BooleanField(
        "注目に出す",
        default=False,
        help_text="スタンプの数にかかわらず、HOMEの「注目」に出します（スタンプの多いものより先に）。",
    )

    featured_order = models.PositiveSmallIntegerField(
        "注目の順番",
        default=10,
        help_text="「注目に出す」ものの並び順。小さい数ほど上（同じ数なら新しい順）。",
    )

    featured_hidden = models.BooleanField(
        "注目から外す",
        default=False,
        help_text="スタンプが多くても、HOMEの「注目」に自動で出さない。",
    )

    publish_at = models.DateTimeField(
        "公開予約",
        null=True,
        blank=True,
        help_text="確認待ちのまま日時を入れると、その時刻に自動で公開されます（スイス時間）。",
    )

    created_at = models.DateTimeField(
        "投稿日時",
        default=timezone.now,
        help_text="一覧はこの日時の新しい順に並びます。確認待ちから公開にすると、公開した時刻になります。",
    )

    updated_at = models.DateTimeField(
        "更新日時",
        auto_now=True,
    )

    class Meta:
        verbose_name = "みんなの投稿"
        verbose_name_plural = "みんなの投稿"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


    @property
    def name(self):
        return self.title

    def shop_codes(self):
        return [code for code in self.shop.split(",") if code]

    def shop_labels(self):
        labels = dict(self.SHOP_CHOICES)
        return [labels.get(code, code) for code in self.shop_codes()]

    def photos(self):
        return [url for url in (self.photo_1, self.photo_2) if url]

    @property
    def photo_slots(self):
        """写真を変える欄: (項目, URL) を2枠"""
        return [("photo_1", self.photo_1), ("photo_2", self.photo_2)]

    def get_absolute_url(self):
        return reverse("washoku:post_detail", args=[self.pk])


def publish_due_posts():
    """
    公開予約の時刻を過ぎた投稿を公開する。投稿日時も公開した時刻にそろえる。
    公開した件数を返す。
    """

    now = timezone.now()
    count = 0

    for post in Post.objects.filter(status="draft", publish_at__lte=now):
        count += Post.objects.filter(pk=post.pk, status="draft").update(
            status="published",
            created_at=post.publish_at,
        )

    return count



# =========================================================
# コメント・Q&A
# =========================================================

class Comment(models.Model):
    """
    レシピ・食材・お店・みんなの投稿のどれか1つに付くコメント。
    返信は1段だけ (parent は返信先のスレッドの先頭コメント)。
    """

    KIND_CHOICES = [
        ("tip", "工夫・コツ"),
        ("question", "質問"),
    ]

    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="comments",
    )

    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="comments",
    )

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="comments",
    )

    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="comments",
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="washoku_comments",
    )

    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
        verbose_name="返信先",
    )

    kind = models.CharField(
        "種類",
        max_length=20,
        choices=KIND_CHOICES,
        default="tip",
    )

    body = models.TextField(
        "本文",
        max_length=500,
    )

    photo_url = models.URLField(
        "写真",
        max_length=500,
        blank=True,
    )

    is_deleted = models.BooleanField(
        "投稿者が削除",
        default=False,
        help_text="返信が付いたコメントは消さずに「削除されました」と表示する。",
    )

    is_hidden = models.BooleanField(
        "非表示",
        default=False,
        help_text="通報で自動的に、または管理者が非表示にしたもの。",
    )

    is_featured = models.BooleanField(
        "注目に出す",
        default=False,
        help_text="スタンプの数にかかわらず、HOMEの「注目」に出します（スタンプの多いものより先に）。",
    )

    featured_order = models.PositiveSmallIntegerField(
        "注目の順番",
        default=10,
        help_text="「注目に出す」ものの並び順。小さい数ほど上（同じ数なら新しい順）。",
    )

    featured_hidden = models.BooleanField(
        "注目から外す",
        default=False,
        help_text="スタンプが多くても、HOMEの「注目」に自動で出さない。",
    )

    reopened = models.BooleanField(
        "未解決に戻す",
        default=False,
        help_text="質問だけ。「確認します」などの返信しかないとき、返信があっても「返事を待っている質問」に出します。",
    )

    admin_checked = models.BooleanField(
        "管理者確認済み",
        default=False,
        db_index=True,
        help_text="管理画面の「対応待ち」に出さないようにするための印。",
    )

    edited_at = models.DateTimeField(
        "編集日時",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        "投稿日時",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "コメント"
        verbose_name_plural = "コメント"
        ordering = ["created_at", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(recipe__isnull=False, ingredient__isnull=True, store__isnull=True, post__isnull=True)
                    | models.Q(recipe__isnull=True, ingredient__isnull=False, store__isnull=True, post__isnull=True)
                    | models.Q(recipe__isnull=True, ingredient__isnull=True, store__isnull=False, post__isnull=True)
                    | models.Q(recipe__isnull=True, ingredient__isnull=True, store__isnull=True, post__isnull=False)
                ),
                name="washoku_comment_has_one_target",
            )
        ]

    def __str__(self):
        return f"{self.author}: {self.body[:30]}"

    @property
    def target(self):
        return self.recipe or self.ingredient or self.store or self.post

    def get_absolute_url(self):

        if self.recipe_id:
            url = reverse("washoku:recipe_detail", args=[self.recipe_id])
        elif self.post_id:
            url = reverse("washoku:post_detail", args=[self.post_id])
        elif self.store_id:
            url = reverse("washoku:store_detail", args=[self.store_id])
        else:
            url = reverse("washoku:ingredient_detail", args=[self.ingredient_id])

        return f"{url}#comment-{self.pk}"


class CommentReport(models.Model):

    # この件数の通報が集まったら自動で非表示にする
    AUTO_HIDE_THRESHOLD = 3

    comment = models.ForeignKey(
        Comment,
        on_delete=models.CASCADE,
        related_name="reports",
    )

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="washoku_reports",
    )

    reason = models.CharField(
        "理由",
        max_length=200,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "通報"
        verbose_name_plural = "通報"
        constraints = [
            models.UniqueConstraint(
                fields=["comment", "reporter"],
                name="washoku_unique_report_per_user",
            )
        ]

    def __str__(self):
        return f"{self.reporter} → {self.comment}"


class Stamp(models.Model):
    """
    コメントとコラムに押せるスタンプ。管理画面で追加・編集・並べ替え・非表示できる。
    """

    key = models.SlugField(
        "ID（英字・あとから変えない）",
        max_length=20,
        unique=True,
    )

    emoji = models.CharField("絵文字", max_length=16)

    label = models.CharField("言葉", max_length=20)

    order = models.PositiveSmallIntegerField("並び順", default=100)

    is_active = models.BooleanField(
        "表示する",
        default=True,
        help_text="外すと選べなくなります（押されたぶんは残ります）",
    )

    class Meta:
        verbose_name = "スタンプ"
        verbose_name_plural = "スタンプ"
        ordering = ["order", "pk"]

    def __str__(self):
        return f"{self.emoji} {self.label}"


class CommentReaction(models.Model):
    """
    コメントへのスタンプ。1人1種類につき1回。
    """

    comment = models.ForeignKey(
        Comment,
        on_delete=models.CASCADE,
        related_name="reactions",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="washoku_reactions",
    )

    kind = models.CharField(
        "種類",
        max_length=20,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "コメントへのスタンプ"
        verbose_name_plural = "コメントへのスタンプ"
        constraints = [
            models.UniqueConstraint(
                fields=["comment", "user", "kind"],
                name="washoku_unique_reaction",
            )
        ]

    def __str__(self):
        return f"{self.user} {self.get_kind_display()} → {self.comment_id}"


class PollChoice(models.Model):
    """
    アンケートの選択肢。
    """

    post = models.ForeignKey(
        "Post",
        on_delete=models.CASCADE,
        related_name="choices",
        limit_choices_to={"kind": "poll"},
    )

    label = models.CharField(
        "選択肢",
        max_length=60,
    )

    order = models.PositiveSmallIntegerField(
        "並び順",
        default=0,
    )

    class Meta:
        verbose_name = "アンケートの選択肢"
        verbose_name_plural = "アンケートの選択肢"
        ordering = ["order", "pk"]

    def __str__(self):
        return self.label


class PollVote(models.Model):
    """
    アンケートの1票。1人1票で、あとから選び直せる。
    """

    post = models.ForeignKey(
        "Post",
        on_delete=models.CASCADE,
        related_name="votes",
    )

    choice = models.ForeignKey(
        PollChoice,
        on_delete=models.CASCADE,
        related_name="votes",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="washoku_poll_votes",
    )

    voted_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "アンケートの票"
        verbose_name_plural = "アンケートの票"
        constraints = [
            models.UniqueConstraint(
                fields=["post", "user"],
                name="washoku_one_vote_per_poll",
            )
        ]

    def __str__(self):
        return f"{self.user} → {self.choice}"


class PostReaction(models.Model):
    """
    コラムへのスタンプ。1人1種類につき1回。
    """

    post = models.ForeignKey(
        "Post",
        on_delete=models.CASCADE,
        related_name="reactions",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="washoku_post_reactions",
    )

    kind = models.CharField(
        "種類",
        max_length=20,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "コラムへのスタンプ"
        verbose_name_plural = "コラムへのスタンプ"
        constraints = [
            models.UniqueConstraint(
                fields=["post", "user", "kind"],
                name="washoku_unique_post_reaction",
            )
        ]

    def __str__(self):
        return f"{self.user} {self.get_kind_display()} → {self.post_id}"


class Notification(models.Model):
    """
    自分のコメントへの返信や、コメント・コラムに押されたスタンプを知らせる。
    """

    KIND_CHOICES = [
        ("reply", "返信"),
        # 2026-10-21 まで: スタンプが「ありがとう」だけだったころの通知
        ("thanks", "ありがとう"),
        ("stamp", "スタンプ"),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="washoku_notifications",
    )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="washoku_sent_notifications",
    )

    # コメントへの返信・スタンプは comment、コラムへのスタンプは post
    comment = models.ForeignKey(
        Comment,
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )

    post = models.ForeignKey(
        "Post",
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )

    kind = models.CharField(
        "種類",
        max_length=20,
        choices=KIND_CHOICES,
        default="reply",
    )

    stamp = models.CharField(
        "スタンプ",
        max_length=20,
        blank=True,
    )

    is_read = models.BooleanField(
        "既読",
        default=False,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "通知"
        verbose_name_plural = "通知"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.actor} → {self.recipient}"

    def _stamp(self):
        if not hasattr(self, "_stamp_cache"):
            self._stamp_cache = Stamp.objects.filter(key=self.stamp).first()
        return self._stamp_cache

    def stamp_emoji(self):
        stamp = self._stamp()
        return stamp.emoji if stamp else ""

    def stamp_label(self):
        stamp = self._stamp()
        return stamp.label if stamp else self.stamp


# =========================================================
# 更新のお知らせ・プッシュ通知
# =========================================================

class Announcement(models.Model):
    """
    HOME の一番上に出す「更新のお知らせ」。管理画面から追加する。
    新しい3件まで表示し、×で閉じたものはその端末では出なくなる。
    """

    SHOW_DAYS = 14
    MAX_SHOWN = 3

    message = models.CharField(
        "お知らせ",
        max_length=200,
    )

    link = models.CharField(
        "リンク先（なくてもOK）",
        max_length=300,
        blank=True,
        help_text="例: /washoku/recipes/?category=europe （本場の洋食の一覧）",
    )

    is_active = models.BooleanField(
        "表示する",
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "更新のお知らせ"
        verbose_name_plural = "更新のお知らせ"
        ordering = ["-created_at"]

    def __str__(self):
        return self.message

    @classmethod
    def current(cls):
        """HOME に出すお知らせ (新しい順、最大 MAX_SHOWN 件)"""

        from datetime import timedelta

        from django.utils import timezone

        since = timezone.now() - timedelta(days=cls.SHOW_DAYS)

        return cls.objects.filter(is_active=True, created_at__gte=since)[:cls.MAX_SHOWN]


class PushSubscription(models.Model):
    """
    返信が来たことをプッシュ通知で知らせる端末 (ログインした会員だけ)。
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="washoku_push_subscriptions",
    )

    endpoint = models.TextField(
        unique=True,
    )

    p256dh = models.TextField()

    auth = models.TextField()

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "プッシュ通知の登録"
        verbose_name_plural = "プッシュ通知の登録"

    def __str__(self):
        return f"{self.user} - {self.pk}"
