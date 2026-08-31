from django.contrib import admin

from .models import (
    Child,
    Country,
    CountryScheduleItem,
    CountryScheduleItemTranslation,
    CountryScheduleVersion,
    CountryTranslation,
    HealthcareProvider,
    VaccinationRecord,
    VaccinationRecordComponent,
    VaccinationSettings,
    VaccineComponent,
    VaccineComponentTranslation,
    VaccinePreparation,
    VaccinePreparationTranslation,
    VaccineProduct,
)


class CountryTranslationInline(admin.TabularInline):
    model = CountryTranslation
    extra = 0


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name_en",
    )

    search_fields = (
        "code",
        "name_en",
    )

    inlines = [
        CountryTranslationInline,
    ]


class VaccineComponentTranslationInline(admin.TabularInline):
    model = VaccineComponentTranslation
    extra = 0


@admin.register(VaccineComponent)
class VaccineComponentAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name_en",
    )

    search_fields = (
        "code",
        "name_en",
    )

    inlines = [
        VaccineComponentTranslationInline,
    ]


class VaccinePreparationTranslationInline(admin.TabularInline):
    model = VaccinePreparationTranslation
    extra = 0


@admin.register(VaccinePreparation)
class VaccinePreparationAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name_en",
        "component_names",
    )

    search_fields = (
        "code",
        "name_en",
    )

    filter_horizontal = (
        "components",
    )

    inlines = [
        VaccinePreparationTranslationInline,
    ]

    def component_names(self, obj):
        return ", ".join(
            obj.components.values_list(
                "name_en",
                flat=True,
            )
        )

    component_names.short_description = "Components"


@admin.register(VaccineProduct)
class VaccineProductAdmin(admin.ModelAdmin):
    list_display = (
        "product_name",
        "manufacturer",
        "preparation",
    )

    search_fields = (
        "product_name",
        "manufacturer",
    )

    list_filter = (
        "preparation",
    )


@admin.register(Child)
class ChildAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "owner",
        "date_of_birth",
        "default_country",
    )

    search_fields = (
        "name",
        "owner__username",
    )

    list_filter = (
        "default_country",
    )


@admin.register(HealthcareProvider)
class HealthcareProviderAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "owner",
        "country",
        "city",
        "last_used_at",
    )

    search_fields = (
        "name",
        "city",
        "owner__username",
    )

    list_filter = (
        "country",
    )


class VaccinationRecordComponentInline(admin.TabularInline):
    model = VaccinationRecordComponent
    extra = 0


@admin.register(VaccinationRecord)
class VaccinationRecordAdmin(admin.ModelAdmin):
    list_display = (
        "child",
        "preparation",
        "vaccination_date",
        "country",
        "healthcare_provider",
    )

    search_fields = (
        "child__name",
        "preparation__name_en",
        "product_name",
        "manufacturer",
        "lot_number",
    )

    list_filter = (
        "country",
        "preparation",
        "vaccination_date",
    )

    date_hierarchy = "vaccination_date"

    inlines = [
        VaccinationRecordComponentInline,
    ]


@admin.register(VaccinationSettings)
class VaccinationSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "ui_language",
        "current_country",
        "doctor_language",
    )


class CountryScheduleItemInline(admin.TabularInline):
    model = CountryScheduleItem
    extra = 0


@admin.register(CountryScheduleVersion)
class CountryScheduleVersionAdmin(admin.ModelAdmin):
    list_display = (
        "country",
        "title",
        "valid_from",
        "valid_until",
        "last_verified_at",
    )

    list_filter = (
        "country",
    )

    inlines = [
        CountryScheduleItemInline,
    ]


class CountryScheduleItemTranslationInline(admin.TabularInline):
    model = CountryScheduleItemTranslation
    extra = 0


@admin.register(CountryScheduleItem)
class CountryScheduleItemAdmin(admin.ModelAdmin):
    list_display = (
        "schedule",
        "name_en",
        "display_age",
        "dose_number",
        "recommended_age_min_days",
    )

    list_filter = (
        "schedule__country",
        "schedule",
    )

    filter_horizontal = (
        "required_components",
    )

    inlines = [
        CountryScheduleItemTranslationInline,
    ]
    