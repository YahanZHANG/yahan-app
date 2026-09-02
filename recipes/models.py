from django.conf import settings
from django.db import models


class Appliance(models.Model):
    """
    調理家電
    例:
    - ホットクック KN-HW16E-R
    - シェフドラム DAC-IA2
    """

    APPLIANCE_TYPES = [
        ("hotcook", "ホットクック"),
        ("chefdrum", "シェフドラム"),
    ]

    appliance_type = models.CharField(
        "種類",
        max_length=20,
        choices=APPLIANCE_TYPES,
    )

    name = models.CharField(
        "表示名",
        max_length=100,
    )

    model_number = models.CharField(
        "型番",
        max_length=50,
        unique=True,
    )

    def __str__(self):
        return f"{self.name} {self.model_number}"


class Ingredient(models.Model):
    """
    食材。
    調味料もIngredientとして登録するが、
    is_seasoning=True のものは「家にある食材検索」では無視する。
    """

    CATEGORY_CHOICES = [
        ("meat", "肉"),
        ("fish", "魚介"),
        ("vegetable", "野菜"),
        ("fruit", "果物"),
        ("egg", "卵"),
        ("dairy", "乳製品"),
        ("soy", "豆・大豆製品"),
        ("grain", "米・麺・穀類"),
        ("mushroom", "きのこ"),
        ("seasoning", "調味料"),
        ("other", "その他"),
    ]

    name = models.CharField(
        "食材名",
        max_length=100,
        unique=True,
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
        help_text="例：牛薄切り肉→牛肉、鶏もも肉→鶏肉。空欄の場合は食材名と同じ扱い。",
    )

    switzerland_availability = models.PositiveSmallIntegerField(
        "スイスでの入手しやすさ",
        default=5,
        help_text="1〜5。5が最も入手しやすい。",
    )

    def __str__(self):
        return self.name


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

    def __str__(self):
        return self.name


class NutritionTag(models.Model):
    """
    「今日は何を摂りたい？」で使う栄養タグ。
    """

    name = models.CharField(
        "栄養",
        max_length=50,
        unique=True,
    )

    display_order = models.PositiveIntegerField(
        "表示順",
        default=0,
    )

    def __str__(self):
        return self.name


class Recipe(models.Model):
    """
    レシピ本体。
    """

    COOKING_MODE_CHOICES = [
        ("auto", "自動調理"),
        ("manual", "手動調理"),
    ]

    CATEGORY_CHOICES = [
        ("japanese", "和食"),
        ("western", "洋食"),
        ("chinese", "中華"),
        ("korean", "韓国料理"),
        ("curry", "カレー"),
        ("soup", "スープ"),
        ("pasta", "パスタ・麺"),
        ("rice", "ご飯もの"),
        ("side", "副菜"),
        ("other", "その他"),
    ]

    name = models.CharField(
        "料理名",
        max_length=200,
    )

    appliance = models.ForeignKey(
        Appliance,
        verbose_name="調理家電",
        on_delete=models.PROTECT,
        related_name="recipes",
    )

    category = models.CharField(
        "料理カテゴリー",
        max_length=20,
        choices=CATEGORY_CHOICES,
        default="other",
    )

    cooking_mode = models.CharField(
        "調理方法",
        max_length=20,
        choices=COOKING_MODE_CHOICES,
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

    # -------------------------
    # 実機での操作
    # -------------------------

    menu_number = models.CharField(
        "メニュー番号",
        max_length=50,
        blank=True,
        help_text="自動メニューの場合。例: 3、1-20など",
    )

    appliance_operation = models.TextField(
        "調理家電の操作方法",
        help_text=(
            "例: メニューを選ぶ → 3番 → スタート / "
            "手動 → 煮物を作る → まぜる → 20分 → スタート"
        ),
    )

    # -------------------------
    # 普通の料理手順
    # -------------------------

    preparation = models.TextField(
        "下ごしらえ・作り方",
        blank=True,
    )

    notes = models.TextField(
        "メモ",
        blank=True,
    )

    # -------------------------
    # 検索用
    # -------------------------

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

    nutrition_tags = models.ManyToManyField(
        NutritionTag,
        verbose_name="栄養タグ",
        blank=True,
        related_name="recipes",
    )

    # -------------------------
    # 出典・信頼性
    # -------------------------

    source_name = models.CharField(
        "出典",
        max_length=200,
        blank=True,
    )

    source_url = models.URLField(
        "出典URL",
        blank=True,
    )

    is_official = models.BooleanField(
        "公式レシピ",
        default=False,
    )

    verified_for_model = models.BooleanField(
        "対象機種で使用可能と確認済み",
        default=False,
    )

    switzerland_score = models.PositiveSmallIntegerField(
        "スイスでの作りやすさ",
        default=5,
        help_text="1〜5。5が最も材料を揃えやすい。",
    )

    is_active = models.BooleanField(
        "表示する",
        default=True,
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
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "appliance"],
                name="unique_recipe_per_appliance",
            )
        ]

    def __str__(self):
        return f"{self.name} / {self.appliance}"


class RecipeIngredient(models.Model):
    """
    レシピと食材の中間テーブル。

    「牛肉 200g」
    「じゃがいも 3個」
    のような情報を保持する。
    """

    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name="recipe_ingredients",
    )

    ingredient = models.ForeignKey(
        Ingredient,
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
        help_text="このレシピ内で食材検索の対象外にする場合はON。",
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
        ordering = ["display_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["recipe", "ingredient"],
                name="unique_ingredient_per_recipe",
            )
        ]

    def __str__(self):
        return f"{self.recipe.name} - {self.ingredient.name}"


class RecipePreference(models.Model):
    """
    ★ お気に入り
    × あまり好まない

    1レシピにつきユーザーごとに1状態だけ持つ。
    """

    PREFERENCE_CHOICES = [
        ("favorite", "お気に入り"),
        ("dislike", "あまり好まない"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recipe_preferences",
    )

    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name="preferences",
    )

    preference = models.CharField(
        "評価",
        max_length=20,
        choices=PREFERENCE_CHOICES,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "recipe"],
                name="unique_recipe_preference_per_user",
            )
        ]

    def __str__(self):
        return (
            f"{self.user} - "
            f"{self.recipe.name} - "
            f"{self.get_preference_display()}"
        )