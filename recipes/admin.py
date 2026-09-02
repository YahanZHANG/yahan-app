from django.contrib import admin

from .models import (
    Appliance,
    Ingredient,
    MoodTag,
    NutritionTag,
    Recipe,
    RecipeIngredient,
    RecipePreference,
)


@admin.register(Appliance)
class ApplianceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "model_number",
        "appliance_type",
    )

    list_filter = (
        "appliance_type",
    )

    search_fields = (
        "name",
        "model_number",
    )
    

@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "switzerland_availability",
    )

    list_filter = (
        "category",
        "switzerland_availability",
    )

    search_fields = (
        "name",
    )

    ordering = (
        "category",
        "name",
    )


@admin.register(MoodTag)
class MoodTagAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "display_order",
    )

    search_fields = (
        "name",
    )

    ordering = (
        "display_order",
        "name",
    )


@admin.register(NutritionTag)
class NutritionTagAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "display_order",
    )

    search_fields = (
        "name",
    )

    ordering = (
        "display_order",
        "name",
    )


class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient

    extra = 1

    autocomplete_fields = (
        "ingredient",
    )

    fields = (
        "ingredient",
        "amount",
        "is_seasoning",
        "is_optional",
        "display_order",
    )

    ordering = (
        "display_order",
        "id",
    )

@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "appliance",
        "category",
        "cooking_mode",
        "cooking_time_minutes",
        "is_make_ahead",
        "is_official",
        "verified_for_model",
        "switzerland_score",
        "is_active",
    )

    list_filter = (
        "appliance",
        "category",
        "cooking_mode",
        "is_make_ahead",
        "is_official",
        "verified_for_model",
        "switzerland_score",
        "is_active",
        "mood_tags",
        "nutrition_tags",
    )

    search_fields = (
        "name",
        "menu_number",
        "source_name",
        "recipe_ingredients__ingredient__name",
    )

    autocomplete_fields = (
        "appliance",
    )

    filter_horizontal = (
        "mood_tags",
        "nutrition_tags",
    )

    inlines = (
        RecipeIngredientInline,
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "基本情報",
            {
                "fields": (
                    "name",
                    "appliance",
                    "category",
                    "cooking_mode",
                    "cooking_time_minutes",
                    "servings",
                )
            },
        ),
        (
            "調理家電の操作",
            {
                "fields": (
                    "menu_number",
                    "appliance_operation",
                )
            },
        ),
        (
            "レシピ",
            {
                "fields": (
                    "preparation",
                    "notes",
                )
            },
        ),
        (
            "提案・検索",
            {
                "fields": (
                    "mood_tags",
                    "nutrition_tags",
                    "switzerland_score",
                )
            },
        ),
        (
            "出典・対応確認",
            {
                "fields": (
                    "source_name",
                    "source_url",
                    "is_official",
                    "verified_for_model",
                    "is_active",
                )
            },
        ),
        (
            "システム情報",
            {
                "classes": (
                    "collapse",
                ),
                "fields": (
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )


@admin.register(RecipePreference)
class RecipePreferenceAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "recipe",
        "preference",
        "updated_at",
    )

    list_filter = (
        "preference",
        "recipe__appliance",
    )

    search_fields = (
        "user__username",
        "recipe__name",
    )

    autocomplete_fields = (
        "recipe",
    )


@admin.register(RecipeIngredient)
class RecipeIngredientAdmin(admin.ModelAdmin):
    list_display = (
        "recipe",
        "ingredient",
        "amount",
        "is_seasoning",
        "is_optional",
        "display_order",
    )

    list_filter = (
        "is_seasoning",
        "is_optional",
        "ingredient__category",
    )

    search_fields = (
        "recipe__name",
        "ingredient__name",
    )

    autocomplete_fields = (
        "recipe",
        "ingredient",
    )