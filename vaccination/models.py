from django.conf import settings
from django.db import models


# =============================================================================
# Country
# =============================================================================

class Country(models.Model):
    """
    国マスタ。

    code:
        CH = Switzerland
        JP = Japan
        CN = China
        DE = Germany
        など
    """

    code = models.CharField(
        max_length=2,
        unique=True,
    )

    name_en = models.CharField(
        max_length=100,
    )

    class Meta:
        ordering = ["name_en"]
        verbose_name_plural = "countries"

    def __str__(self):
        return self.name_en

    def get_name(self, language_code="en"):
        translation = self.translations.filter(
            language_code=language_code,
        ).first()

        if translation:
            return translation.name

        return self.name_en


class CountryTranslation(models.Model):
    """
    国名の翻訳。

    例:
    CH
      ja -> スイス
      en -> Switzerland
      de -> Schweiz
      zh-hans -> 瑞士
    """

    country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name="translations",
    )

    language_code = models.CharField(
        max_length=20,
    )

    name = models.CharField(
        max_length=100,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "country",
                    "language_code",
                ],
                name="unique_country_translation",
            )
        ]

    def __str__(self):
        return (
            f"{self.country.code} / "
            f"{self.language_code} / "
            f"{self.name}"
        )


# =============================================================================
# Child
# =============================================================================

class Child(models.Model):
    """
    接種記録を管理する子ども。

    将来、兄弟姉妹を追加できるように
    最初から複数人対応にする。
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="vaccination_children",
    )

    name = models.CharField(
        max_length=150,
    )

    name_en = models.CharField(
        max_length=150,
        blank=True,
        default="",
    )

    date_of_birth = models.DateField()

    birth_country = models.ForeignKey(
        Country,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vaccination_birth_children",
    )

    default_country = models.ForeignKey(
        Country,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vaccination_resident_children",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "date_of_birth",
            "name",
        ]

    def __str__(self):
        return self.name


# =============================================================================
# Vaccine components
# =============================================================================

class VaccineComponent(models.Model):
    """
    ワクチンを「何の感染症に対するものか」という
    成分単位で管理する。

    例:
        DIPHTHERIA
        TETANUS
        PERTUSSIS
        POLIO
        HIB
        HEPATITIS_B
        MEASLES
        MUMPS
        RUBELLA

    MMRなら
        MEASLES
        MUMPS
        RUBELLA

    の3成分を含む。
    """

    code = models.CharField(
        max_length=80,
        unique=True,
    )

    name_en = models.CharField(
        max_length=150,
    )

    class Meta:
        ordering = ["name_en"]

    def __str__(self):
        return self.name_en

    def get_name(self, language_code="en"):
        translation = self.translations.filter(
            language_code=language_code,
        ).first()

        if translation:
            return translation.name

        return self.name_en


class VaccineComponentTranslation(models.Model):
    """
    ワクチン成分名の翻訳。

    例:
    JAPANESE_ENCEPHALITIS

        ja
        日本脳炎

        en
        Japanese encephalitis

        de
        Japanische Enzephalitis

        zh-hans
        流行性乙型脑炎
    """

    component = models.ForeignKey(
        VaccineComponent,
        on_delete=models.CASCADE,
        related_name="translations",
    )

    language_code = models.CharField(
        max_length=20,
    )

    name = models.CharField(
        max_length=150,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "component",
                    "language_code",
                ],
                name="unique_vaccine_component_translation",
            )
        ]

    def __str__(self):
        return (
            f"{self.component.code} / "
            f"{self.language_code}"
        )


# =============================================================================
# Vaccine preparation
# =============================================================================

class VaccinePreparation(models.Model):
    """
    実際に接種するワクチンの「組み合わせ」。

    例:

    MMR
        Measles
        Mumps
        Rubella

    DTaP-IPV
        Diphtheria
        Tetanus
        Pertussis
        Polio

    DTaP-IPV-Hib
        Diphtheria
        Tetanus
        Pertussis
        Polio
        Hib

    DTaP-IPV-Hib-HepB
        Diphtheria
        Tetanus
        Pertussis
        Polio
        Hib
        Hepatitis B
    """

    code = models.CharField(
        max_length=100,
        unique=True,
    )

    name_en = models.CharField(
        max_length=200,
    )

    components = models.ManyToManyField(
        VaccineComponent,
        related_name="preparations",
    )

    class Meta:
        ordering = ["name_en"]

    def __str__(self):
        return self.name_en

    def get_name(self, language_code="en"):
        translation = self.translations.filter(
            language_code=language_code,
        ).first()

        if translation:
            return translation.name

        return self.name_en


class VaccinePreparationTranslation(models.Model):
    """
    混合ワクチン名の翻訳。
    """

    preparation = models.ForeignKey(
        VaccinePreparation,
        on_delete=models.CASCADE,
        related_name="translations",
    )

    language_code = models.CharField(
        max_length=20,
    )

    name = models.CharField(
        max_length=200,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "preparation",
                    "language_code",
                ],
                name="unique_vaccine_preparation_translation",
            )
        ]

    def __str__(self):
        return (
            f"{self.preparation.code} / "
            f"{self.language_code}"
        )


# =============================================================================
# Vaccine product
# =============================================================================

class VaccineProduct(models.Model):
    """
    実際の商品。

    例:
        Infanrix hexa
        Priorix
        Engerix-B

    同じワクチン構成でも
    メーカー・商品名が異なることがある。
    """

    preparation = models.ForeignKey(
        VaccinePreparation,
        on_delete=models.CASCADE,
        related_name="products",
    )

    product_name = models.CharField(
        max_length=200,
    )

    manufacturer = models.CharField(
        max_length=200,
        blank=True,
    )

    def __str__(self):
        if self.manufacturer:
            return (
                f"{self.product_name} "
                f"({self.manufacturer})"
            )

        return self.product_name


# =============================================================================
# Healthcare provider
# =============================================================================

class HealthcareProvider(models.Model):
    """
    接種した病院・小児科・クリニックなど。

    一度入力した医療機関を保存し、
    次の接種登録時には候補から選べるようにする。
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="vaccination_healthcare_providers",
    )

    name = models.CharField(
        max_length=200,
    )

    country = models.ForeignKey(
        Country,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="healthcare_providers",
    )

    city = models.CharField(
        max_length=100,
        blank=True,
    )

    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = [
            "-last_used_at",
            "name",
        ]

    def __str__(self):
        return self.name


# =============================================================================
# Vaccination record
# =============================================================================

class VaccinationRecord(models.Model):
    """
    実際に行った「1回の接種」。

    例えば6種混合を1本打ったなら、
    VaccinationRecordは1件だけ。

    その中に含まれる6成分は、
    VaccinationRecordComponentとして別管理する。
    """

    child = models.ForeignKey(
        Child,
        on_delete=models.CASCADE,
        related_name="vaccination_records",
    )

    preparation = models.ForeignKey(
        VaccinePreparation,
        on_delete=models.PROTECT,
        related_name="vaccination_records",
    )

    vaccination_date = models.DateField()

    country = models.ForeignKey(
        Country,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vaccination_records",
    )

    healthcare_provider = models.ForeignKey(
        HealthcareProvider,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vaccination_records",
    )

    product = models.ForeignKey(
        VaccineProduct,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vaccination_records",
    )

    # 商品マスタに存在しない製品でも記録できるようにする
    product_name = models.CharField(
        max_length=200,
        blank=True,
    )

    manufacturer = models.CharField(
        max_length=200,
        blank=True,
    )

    lot_number = models.CharField(
        max_length=100,
        blank=True,
    )

    # 「この製剤として何回目か」
    #
    # 成分ごとの接種回数とは別。
    preparation_dose_number = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )

    no_reaction = models.BooleanField(
        default=False,
    )

    # 例:
    # [
    #     "fever",
    #     "swelling"
    # ]
    reaction_codes = models.JSONField(
        default=list,
        blank=True,
    )

    reaction_other = models.CharField(
        max_length=300,
        blank=True,
    )

    notes = models.TextField(
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-vaccination_date",
            "-id",
        ]

    def __str__(self):
        return (
            f"{self.child.name} - "
            f"{self.preparation.name_en} - "
            f"{self.vaccination_date}"
        )


# =============================================================================
# Vaccination record components
# =============================================================================

class VaccinationRecordComponent(models.Model):
    """
    1回の接種に含まれていた各成分。

    例:

    Infanrix hexaを1本接種
        ↓

    VaccinationRecord
        Infanrix hexa

    VaccinationRecordComponent
        Diphtheria
        Tetanus
        Pertussis
        Polio
        Hib
        Hepatitis B


    dose_numberは成分ごとに持つ。

    これが重要。

    例えばHepatitis Bだけ出生時にすでに1回打っていた場合、

    6種混合を初めて打っても

        DTaP = 1回目
        IPV = 1回目
        Hib = 1回目
        HepB = 2回目

    のようなケースに対応できる。
    """

    record = models.ForeignKey(
        VaccinationRecord,
        on_delete=models.CASCADE,
        related_name="record_components",
    )

    component = models.ForeignKey(
        VaccineComponent,
        on_delete=models.PROTECT,
        related_name="vaccination_record_components",
    )

    dose_number = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "record",
                    "component",
                ],
                name="unique_vaccination_record_component",
            )
        ]

        ordering = [
            "component__name_en",
        ]

    def __str__(self):
        return (
            f"{self.record} / "
            f"{self.component.code}"
        )


# =============================================================================
# Country vaccination schedule
# =============================================================================

class CountryScheduleVersion(models.Model):
    """
    国別予防接種スケジュール。

    国のスケジュールは将来変更されるため、
    バージョンを残す。

    例:
        Switzerland 2026
        Japan FY2026
    """

    country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name="vaccination_schedule_versions",
    )

    title = models.CharField(
        max_length=200,
    )

    valid_from = models.DateField()

    valid_until = models.DateField(
        null=True,
        blank=True,
    )

    source_name = models.CharField(
        max_length=250,
        blank=True,
    )

    source_url = models.URLField(
        blank=True,
    )

    last_verified_at = models.DateField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = [
            "country",
            "-valid_from",
        ]

    def __str__(self):
        return (
            f"{self.country.code} - "
            f"{self.title}"
        )


class CountryScheduleItem(models.Model):
    """
    国別スケジュールの1項目。

    preparationそのものではなく、
    required_componentsで判定する。

    これにより、

    スイスで6種混合
    日本で4種混合 + Hib + HepB

    のように違う方法で打っても、
    同じ成分が接種済みか比較できる。
    """

    schedule = models.ForeignKey(
        CountryScheduleVersion,
        on_delete=models.CASCADE,
        related_name="items",
    )

    code = models.CharField(
        max_length=100,
    )

    name_en = models.CharField(
        max_length=200,
    )

    required_components = models.ManyToManyField(
        VaccineComponent,
        related_name="country_schedule_items",
    )

    applies_to_product = models.ForeignKey(
        VaccineProduct,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="country_schedule_items",
    )

    recommended_age_min_days = models.PositiveIntegerField()

    recommended_age_max_days = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    recommended_interval_min_days = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    recommended_interval_max_days = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    recommended_interval_from_dose_number = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    display_age = models.CharField(
        max_length=100,
        blank=True,
        help_text="例: 2か月、9か月、12か月",
    )

    dose_number = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )

    note = models.TextField(
        blank=True,
    )

    sort_order = models.PositiveIntegerField(
        default=0,
    )

    class Meta:
        ordering = [
            "recommended_age_min_days",
            "sort_order",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "schedule",
                    "code",
                ],
                name="unique_country_schedule_item",
            )
        ]

    def __str__(self):
        return (
            f"{self.schedule.country.code} - "
            f"{self.name_en}"
        )

    def get_name(self, language_code="en"):
        translation = self.translations.filter(
            language_code=language_code,
        ).first()

        if translation:
            return translation.name

        return self.name_en


class CountryScheduleItemTranslation(models.Model):
    """
    国別スケジュール上の表示名・説明の翻訳。
    """

    schedule_item = models.ForeignKey(
        CountryScheduleItem,
        on_delete=models.CASCADE,
        related_name="translations",
    )

    language_code = models.CharField(
        max_length=20,
    )

    name = models.CharField(
        max_length=200,
    )

    note = models.TextField(
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "schedule_item",
                    "language_code",
                ],
                name="unique_country_schedule_item_translation",
            )
        ]

    def __str__(self):
        return (
            f"{self.schedule_item.code} / "
            f"{self.language_code}"
        )


# =============================================================================
# User settings
# =============================================================================

class VaccinationSettings(models.Model):
    """
    予防接種アプリ専用設定。
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="vaccination_settings",
    )

    active_child = models.ForeignKey(
        Child,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="active_vaccination_settings",
    )

    # ja / en / de / zh-hans
    #
    # choicesをModel側には固定しない。
    # 将来言語を増やしてもmigration不要にするため。
    ui_language = models.CharField(
        max_length=20,
        default="ja",
    )

    current_country = models.ForeignKey(
        Country,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    doctor_language = models.CharField(
        max_length=20,
        default="en",
    )

    doctor_show_english = models.BooleanField(
        default=True,
    )

    DATE_FORMAT_CHOICES = [
        ("ymd", "2026/08/31"),
        ("dmy_dot", "31.08.2026"),
        ("dmy_text", "31 Aug 2026"),
    ]

    date_format = models.CharField(
        max_length=20,
        choices=DATE_FORMAT_CHOICES,
        default="ymd",
    )

    def __str__(self):
        return f"Vaccination settings: {self.user}"


class ChildCollaborator(models.Model):

    PERMISSION_EDIT = "edit"
    PERMISSION_VIEW = "view"

    PERMISSION_CHOICES = [
        (
            PERMISSION_EDIT,
            "Can edit",
        ),
        (
            PERMISSION_VIEW,
            "View only",
        ),
    ]

    child = models.ForeignKey(
        Child,
        on_delete=models.CASCADE,
        related_name="collaborators",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="vaccination_collaborations",
    )

    permission = models.CharField(
        max_length=20,
        choices=PERMISSION_CHOICES,
        default=PERMISSION_EDIT,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "child",
                    "user",
                ],
                name="unique_child_collaborator",
            ),
        ]

    def __str__(self):
        return (
            f"{self.child.name} - "
            f"{self.user.username} "
            f"({self.permission})"
        )