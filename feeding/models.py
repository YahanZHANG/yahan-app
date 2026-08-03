from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

class Baby(models.Model):
    """アプリで管理する赤ちゃん。"""

    name = models.CharField(
        "名前",
        max_length=50,
    )
    birth_date = models.DateField(
        "生年月日",
    )
    caregivers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="BabyMembership",
        related_name="feeding_babies",
        verbose_name="管理ユーザー",
        blank=True,
    )
    created_at = models.DateTimeField(
        "作成日時",
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        "更新日時",
        auto_now=True,
    )

    class Meta:
        verbose_name = "赤ちゃん"
        verbose_name_plural = "赤ちゃん"
        ordering = [
            "birth_date",
            "name",
        ]

    def __str__(self):
        return self.name

class BabyMembership(models.Model):
    """赤ちゃんと、その情報を管理できるユーザーの関係。"""

    baby = models.ForeignKey(
        Baby,
        verbose_name="赤ちゃん",
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ユーザー",
        on_delete=models.CASCADE,
        related_name="baby_memberships",
    )
    can_edit = models.BooleanField(
        "編集できる",
        default=True,
    )
    created_at = models.DateTimeField(
        "登録日時",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "赤ちゃんの利用者"
        verbose_name_plural = "赤ちゃんの利用者"
        ordering = [
            "baby",
            "user__username",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "baby",
                    "user",
                ],
                name="unique_user_per_baby",
            ),
        ]

    def __str__(self):
        return (
            f"{self.baby.name}："
            f"{self.user.username}"
        )

class FoodCategory(models.Model):
    """野菜、果物、肉類などの食材ジャンル。"""

    name = models.CharField(
        "ジャンル名",
        max_length=50,
        unique=True,
    )
    display_order = models.PositiveIntegerField(
        "表示順",
        default=0,
    )
    is_active = models.BooleanField(
        "表示する",
        default=True,
    )

    class Meta:
        verbose_name = "食材ジャンル"
        verbose_name_plural = "食材ジャンル"
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name

class FeedingGroup(models.Model):
    """月齢別の標準量と比較するための食品群。"""

    class Code(models.TextChoices):
        GRAIN = "grain", "穀類"
        VEGETABLE_FRUIT = "vegetable_fruit", "野菜・果物"
        FISH = "fish", "魚"
        MEAT = "meat", "肉"
        TOFU = "tofu", "豆腐"
        EGG = "egg", "卵"
        DAIRY = "dairy", "乳製品"
        OTHER = "other", "比較対象外"

    code = models.CharField(
        "コード",
        max_length=30,
        choices=Code.choices,
        unique=True,
    )
    name = models.CharField(
        "食品群名",
        max_length=50,
    )
    display_order = models.PositiveIntegerField(
        "表示順",
        default=0,
    )
    is_active = models.BooleanField(
        "表示する",
        default=True,
    )

    class Meta:
        verbose_name = "標準量用食品群"
        verbose_name_plural = "標準量用食品群"
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name

class FeedingGuideline(models.Model):
    """月齢別・食品群別の1食あたり目安量。"""

    class Unit(models.TextChoices):
        GRAM = "g", "g"
        EGG = "egg", "個"

    min_age_months = models.PositiveSmallIntegerField(
        "開始月齢",
    )
    max_age_months = models.PositiveSmallIntegerField(
        "終了月齢",
    )
    feeding_group = models.ForeignKey(
        FeedingGroup,
        verbose_name="食品群",
        on_delete=models.CASCADE,
        related_name="guidelines",
    )
    minimum_amount = models.DecimalField(
        "最小量",
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
    )
    maximum_amount = models.DecimalField(
        "最大量",
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
    )
    unit = models.CharField(
        "単位",
        max_length=10,
        choices=Unit.choices,
        default=Unit.GRAM,
    )
    food_form_note = models.CharField(
        "食品形態・補足",
        max_length=200,
        blank=True,
    )
    display_note = models.CharField(
        "表示用注記",
        max_length=200,
        blank=True,
    )
    display_order = models.PositiveIntegerField(
        "表示順",
        default=0,
    )

    class Meta:
        verbose_name = "月齢別標準量"
        verbose_name_plural = "月齢別標準量"
        ordering = [
            "min_age_months",
            "display_order",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "min_age_months",
                    "max_age_months",
                    "feeding_group",
                ],
                name="unique_guideline_per_age_and_group",
            ),
        ]

    def __str__(self):
        return (
            f"{self.min_age_months}〜"
            f"{self.max_age_months}か月・"
            f"{self.feeding_group.name}"
        )

class Allergen(models.Model):
    """食品表示法上のアレルゲン品目。"""

    class Classification(models.TextChoices):
        REQUIRED = "required", "義務表示"
        RECOMMENDED = "recommended", "推奨表示"

    name = models.CharField(
        "アレルゲン名",
        max_length=50,
        unique=True,
    )
    classification = models.CharField(
        "区分",
        max_length=20,
        choices=Classification.choices,
    )
    display_order = models.PositiveIntegerField(
        "表示順",
        default=0,
    )
    is_active = models.BooleanField(
        "表示する",
        default=True,
    )

    class Meta:
        verbose_name = "アレルゲン"
        verbose_name_plural = "アレルゲン"
        ordering = ["classification", "display_order", "name"]

    def __str__(self):
        return self.name

class Food(models.Model):
    """にんじん、豆腐、牛肉などの単一食材。"""

    name = models.CharField(
        "食材名",
        max_length=100,
        unique=True,
    )
    category = models.ForeignKey(
        FoodCategory,
        verbose_name="ジャンル",
        on_delete=models.PROTECT,
        related_name="foods",
    )
    feeding_group = models.ForeignKey(
        FeedingGroup,
        verbose_name="標準量用食品群",
        on_delete=models.PROTECT,
        related_name="foods",
        null=True,
        blank=True,
    )
    
    allergens = models.ManyToManyField(
        Allergen,
        verbose_name="アレルゲン",
        related_name="foods",
        blank=True,
    )
    is_user_created = models.BooleanField(
        "手動追加した食材",
        default=False,
    )
    show_in_first_year_list = models.BooleanField(
        "1歳までリストに表示",
        default=True,
    )
    is_active = models.BooleanField(
        "表示する",
        default=True,
    )
    created_at = models.DateTimeField(
        "作成日時",
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        "更新日時",
        auto_now=True,
    )

    class Meta:
        verbose_name = "食材"
        verbose_name_plural = "食材"
        ordering = ["category__display_order", "category__name", "name"]

    def __str__(self):
        return self.name

class DishCategory(models.Model):
    """おかゆ、麺・パスタ、魚料理などの料理ジャンル。"""

    name = models.CharField(
        "料理ジャンル名",
        max_length=50,
        unique=True,
    )
    display_order = models.PositiveIntegerField(
        "表示順",
        default=0,
    )
    is_active = models.BooleanField(
        "表示する",
        default=True,
    )

    class Meta:
        verbose_name = "料理ジャンル"
        verbose_name_plural = "料理ジャンル"
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name

class Dish(models.Model):
    """ボロネーゼ、野菜がゆなどの料理。"""

    name = models.CharField(
        "料理名",
        max_length=100,
        unique=True,
    )
    category = models.ForeignKey(
        DishCategory,
        verbose_name="料理ジャンル",
        on_delete=models.PROTECT,
        related_name="dishes",
    )

    finished_amount_g = models.DecimalField(
        "完成量",
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(0.01),
        ],
        help_text=(
            "調理後に完成した料理全体の重量をgで入力する。"
        ),
    )

    instructions = models.TextField(
        "作り方",
        blank=True,
    )

    ingredients = models.ManyToManyField(
        Food,
        verbose_name="含まれる食材",
        through="DishIngredient",
        related_name="dishes",
        blank=True,
    )
    is_user_created = models.BooleanField(
        "手動追加した料理",
        default=False,
    )
    is_active = models.BooleanField(
        "表示する",
        default=True,
    )
    created_at = models.DateTimeField(
        "作成日時",
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        "更新日時",
        auto_now=True,
    )

    class Meta:
        verbose_name = "料理"
        verbose_name_plural = "料理"
        ordering = ["category__display_order", "category__name", "name"]

    def __str__(self):
        return self.name

    @property
    def allergens(self):
        """料理に含まれる食材からアレルゲンを取得する。"""
        return Allergen.objects.filter(
            foods__dishes=self
        ).distinct()

class DishIngredient(models.Model):
    """料理と、その料理に含まれる食材の関係。"""

    dish = models.ForeignKey(
        Dish,
        verbose_name="料理",
        on_delete=models.CASCADE,
        related_name="dish_ingredients",
    )
    food = models.ForeignKey(
        Food,
        verbose_name="食材",
        on_delete=models.PROTECT,
        related_name="dish_ingredients",
    )
    amount_g = models.DecimalField(
        "使用量",
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(0.01),
        ],
        help_text=(
            "料理全体に使用した材料の重量をgで入力する。"
        ),
    )
    display_order = models.PositiveIntegerField(
        "表示順",
        default=0,
        validators=[MinValueValidator(0)],
    )

    class Meta:
        verbose_name = "料理の材料"
        verbose_name_plural = "料理の材料"
        ordering = ["display_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["dish", "food"],
                name="unique_food_per_dish",
            ),
        ]

    def __str__(self):
        return f"{self.dish.name}：{self.food.name}"

class Meal(models.Model):
    """赤ちゃんの1回分の食事。"""

    class MealNumber(models.IntegerChoices):
        FIRST = 1, "1食目"
        SECOND = 2, "2食目"
        THIRD = 3, "3食目"

    baby = models.ForeignKey(
        Baby,
        verbose_name="赤ちゃん",
        on_delete=models.CASCADE,
        related_name="meals",
    )
    date = models.DateField(
        "日付",
    )
    meal_number = models.PositiveSmallIntegerField(
        "食事番号",
        choices=MealNumber.choices,
    )
    created_at = models.DateTimeField(
        "作成日時",
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        "更新日時",
        auto_now=True,
    )

    class Meta:
        verbose_name = "食事記録"
        verbose_name_plural = "食事記録"
        ordering = [
            "-date",
            "meal_number",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "baby",
                    "date",
                    "meal_number",
                ],
                name="unique_meal_per_baby_date_number",
            ),
        ]

    def __str__(self):
        return (
            f"{self.baby.name}・"
            f"{self.date:%Y年%m月%d日}・"
            f"{self.get_meal_number_display()}"
        )


class MealItem(models.Model):
    """1回の食事に含まれる食材または料理。"""

    class ItemType(models.TextChoices):
        FOOD = "food", "食材"
        DISH = "dish", "料理"

    class Unit(models.TextChoices):
        GRAM = "g", "g"
        MILLILITER = "ml", "ml"
        TEASPOON = "tsp", "小さじ"
        TABLESPOON = "tbsp", "大さじ"

    class Reaction(models.TextChoices):
        LOVE = "love", "大喜び"
        HAPPY = "happy", "嬉"
        NORMAL = "normal", "普"
        UNSURE = "unsure", "微妙"

    meal = models.ForeignKey(
        Meal,
        verbose_name="食事記録",
        on_delete=models.CASCADE,
        related_name="items",
    )
    item_type = models.CharField(
        "種類",
        max_length=10,
        choices=ItemType.choices,
    )
    food = models.ForeignKey(
        Food,
        verbose_name="食材",
        on_delete=models.PROTECT,
        related_name="meal_items",
        null=True,
        blank=True,
    )
    dish = models.ForeignKey(
        Dish,
        verbose_name="料理",
        on_delete=models.PROTECT,
        related_name="meal_items",
        null=True,
        blank=True,
    )
    amount = models.DecimalField(
        "実際に食べた量",
        max_digits=7,
        decimal_places=2,
        validators=[
            MinValueValidator(0.01),
        ],
    )
    unit = models.CharField(
        "単位",
        max_length=10,
        choices=Unit.choices,
    )
    reaction = models.CharField(
        "反応",
        max_length=10,
        choices=Reaction.choices,
        blank=True,
        default="",
    )
    has_allergy_symptoms = models.BooleanField(
        "症状あり",
        default=False,
    )
    display_order = models.PositiveIntegerField(
        "表示順",
        default=0,
    )
    created_at = models.DateTimeField(
        "作成日時",
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        "更新日時",
        auto_now=True,
    )

    class Meta:
        verbose_name = "食事内容"
        verbose_name_plural = "食事内容"
        ordering = [
            "display_order",
            "id",
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        item_type="food",
                        food__isnull=False,
                        dish__isnull=True,
                    )
                    | models.Q(
                        item_type="dish",
                        food__isnull=True,
                        dish__isnull=False,
                    )
                ),
                name="meal_item_matches_selected_type",
            ),
        ]

    def __str__(self):
        return (
            f"{self.meal}："
            f"{self.item_name}"
        )

    @property
    def item_name(self):
        if self.item_type == self.ItemType.FOOD and self.food:
            return self.food.name

        if self.item_type == self.ItemType.DISH and self.dish:
            return self.dish.name

        return "未選択"

    @property
    def allergen_names(self):
        """この食事内容に含まれるアレルゲン名を返す。"""

        if (
            self.item_type == self.ItemType.FOOD
            and self.food_id
        ):
            return list(
                self.food.allergens
                .filter(is_active=True)
                .order_by("display_order", "name")
                .values_list("name", flat=True)
            )

        if (
            self.item_type == self.ItemType.DISH
            and self.dish_id
        ):
            return list(
                Allergen.objects
                .filter(
                    foods__meal_item_ingredient_snapshots__meal_item=self,
                    is_active=True,
                )
                .distinct()
                .order_by("display_order", "name")
                .values_list("name", flat=True)
            )

        return []

    @property
    def contains_allergen(self):
        """アレルゲンを1つ以上含むか返す。"""
        return bool(self.allergen_names)

    def clean(self):
        super().clean()

        errors = {}

        if self.item_type == self.ItemType.FOOD:
            if self.food_id is None:
                errors["food"] = "食材を選択してください。"

            if self.dish_id is not None:
                errors["dish"] = (
                    "食材を記録する場合は、料理を選択できません。"
                )

        elif self.item_type == self.ItemType.DISH:
            if self.dish_id is None:
                errors["dish"] = "料理を選択してください。"

            if self.food_id is not None:
                errors["food"] = (
                    "料理を記録する場合は、食材を選択できません。"
                )

        if errors:
            raise ValidationError(errors)

    def create_ingredient_snapshot(self):
        """
        料理を記録した時点の材料と、
        実際に食べた材料量を保存する。
        """
        self.ingredient_snapshots.all().delete()

        if (
            self.item_type != self.ItemType.DISH
            or self.dish_id is None
        ):
            return

        ingredients = (
            self.dish.dish_ingredients
            .select_related("food")
            .order_by("display_order", "id")
        )

        finished_amount = self.dish.finished_amount_g

        snapshots = []

        for ingredient in ingredients:
            calculated_amount = None

            if (
                self.unit == self.Unit.GRAM
                and finished_amount
                and finished_amount > 0
                and ingredient.amount_g
                and ingredient.amount_g > 0
            ):
                calculated_amount = (
                    ingredient.amount_g
                    * self.amount
                    / finished_amount
                )

            snapshots.append(
                MealItemIngredient(
                    meal_item=self,
                    food=ingredient.food,
                    amount_g=calculated_amount,
                    display_order=ingredient.display_order,
                )
            )

        MealItemIngredient.objects.bulk_create(
            snapshots
        )
    
class MealItemIngredient(models.Model):
    """
    料理を食事記録へ追加した時点の材料一覧。

    後で料理マスターを変更しても、
    過去の食事内容が変わらないようにする。
    """

    meal_item = models.ForeignKey(
        MealItem,
        verbose_name="食事内容",
        on_delete=models.CASCADE,
        related_name="ingredient_snapshots",
    )
    food = models.ForeignKey(
        Food,
        verbose_name="食材",
        on_delete=models.PROTECT,
        related_name="meal_item_ingredient_snapshots",
    )
    amount_g = models.DecimalField(
        "実際に食べた材料量",
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(0.01),
        ],
    )
    display_order = models.PositiveIntegerField(
        "表示順",
        default=0,
    )

    class Meta:
        verbose_name = "食事時点の料理材料"
        verbose_name_plural = "食事時点の料理材料"
        ordering = [
            "display_order",
            "id",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "meal_item",
                    "food",
                ],
                name="unique_food_per_meal_item_snapshot",
            ),
        ]

    def __str__(self):
        return (
            f"{self.meal_item.item_name}："
            f"{self.food.name}"
        )


class AllergyReaction(models.Model):
    """食材・料理を食べた後に生じた症状の詳細記録。"""

    meal_item = models.OneToOneField(
        MealItem,
        verbose_name="食事内容",
        on_delete=models.CASCADE,
        related_name="allergy_reaction",
    )
    onset_time = models.TimeField(
        "症状が出た時刻",
        null=True,
        blank=True,
    )
    minutes_after_eating = models.PositiveIntegerField(
        "食後何分で症状が出たか",
        null=True,
        blank=True,
    )
    symptoms = models.JSONField(
        "症状",
        default=list,
        blank=True,
    )
    body_locations = models.JSONField(
        "症状が出た場所",
        default=list,
        blank=True,
    )
    other_symptom = models.CharField(
        "その他の症状",
        max_length=255,
        blank=True,
    )
    other_location = models.CharField(
        "その他の場所",
        max_length=255,
        blank=True,
    )
    visited_doctor = models.BooleanField(
        "受診した",
        default=False,
    )
    medical_institution = models.CharField(
        "医療機関名",
        max_length=200,
        blank=True,
    )
    doctor_diagnosis = models.TextField(
        "医師の診断",
        blank=True,
    )
    doctor_instructions = models.TextField(
        "医師からの指示",
        blank=True,
    )
    avoidance_instructed = models.BooleanField(
        "除去を指示された",
        default=False,
    )
    notes = models.TextField(
        "メモ",
        blank=True,
    )
    created_at = models.DateTimeField(
        "作成日時",
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        "更新日時",
        auto_now=True,
    )

    class Meta:
        verbose_name = "アレルギー症状"
        verbose_name_plural = "アレルギー症状"
        ordering = ["-meal_item__meal__date", "-created_at"]

    def __str__(self):
        return (
            f"{self.meal_item.item_name}・"
            f"{self.meal_item.meal.date:%Y年%m月%d日}"
        )


class AllergyReactionPhoto(models.Model):
    """アレルギー症状の写真。"""

    reaction = models.ForeignKey(
        AllergyReaction,
        verbose_name="アレルギー症状",
        on_delete=models.CASCADE,
        related_name="photos",
    )
    image = models.ImageField(
        "写真",
        upload_to="allergy_reactions/%Y/%m/",
    )
    created_at = models.DateTimeField(
        "登録日時",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "アレルギー症状の写真"
        verbose_name_plural = "アレルギー症状の写真"
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.reaction}の写真"