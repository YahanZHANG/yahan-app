from django.contrib import admin

from .models import (
    Allergen,
    AllergyReaction,
    AllergyReactionPhoto,
    Baby,
    Dish,
    DishCategory,
    DishIngredient,
    FeedingGroup,
    FeedingGuideline,
    Food,
    FoodCategory,
    Meal,
    MealItem,
    MealItemIngredient,
    
)


@admin.register(Baby)
class BabyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "birth_date",
        "updated_at",
    )
    search_fields = ("name",)
    ordering = ("birth_date",)


@admin.register(FoodCategory)
class FoodCategoryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "display_order",
        "is_active",
    )
    list_editable = (
        "display_order",
        "is_active",
    )
    search_fields = ("name",)
    ordering = (
        "display_order",
        "name",
    )


@admin.register(Allergen)
class AllergenAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "classification",
        "display_order",
        "is_active",
    )
    list_filter = (
        "classification",
        "is_active",
    )
    list_editable = (
        "display_order",
        "is_active",
    )
    search_fields = ("name",)
    ordering = (
        "classification",
        "display_order",
        "name",
    )


@admin.register(Food)
class FoodAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "feeding_group",
        "allergen_names",
        "show_in_first_year_list",
        "is_user_created",
        "is_active",
    )
    list_filter = (
        "category",
        "feeding_group",
        "show_in_first_year_list",
        "is_user_created",
        "is_active",
        "allergens",
    )
    search_fields = (
        "name",
        "category__name",
    )
    filter_horizontal = ("allergens",)
    list_select_related = ("category",)
    ordering = (
        "category__display_order",
        "category__name",
        "name",
    )

    @admin.display(description="アレルゲン")
    def allergen_names(self, obj):
        return "、".join(
            obj.allergens.values_list("name", flat=True)
        ) or "なし"


@admin.register(DishCategory)
class DishCategoryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "display_order",
        "is_active",
    )
    list_editable = (
        "display_order",
        "is_active",
    )
    search_fields = ("name",)
    ordering = (
        "display_order",
        "name",
    )


class DishIngredientInline(admin.TabularInline):
    model = DishIngredient
    extra = 3
    autocomplete_fields = ("food",)
    ordering = ("display_order",)


@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "ingredient_names",
        "allergen_names",
        "is_user_created",
        "is_active",
    )
    list_filter = (
        "category",
        "is_user_created",
        "is_active",
    )
    search_fields = (
        "name",
        "category__name",
        "dish_ingredients__food__name",
    )
    list_select_related = ("category",)
    inlines = (DishIngredientInline,)
    ordering = (
        "category__display_order",
        "category__name",
        "name",
    )

    @admin.display(description="材料")
    def ingredient_names(self, obj):
        return "、".join(
            obj.dish_ingredients.select_related("food")
            .order_by("display_order", "id")
            .values_list("food__name", flat=True)
        ) or "未登録"

    @admin.display(description="アレルゲン")
    def allergen_names(self, obj):
        return "、".join(
            obj.allergens.values_list("name", flat=True)
        ) or "なし"


@admin.register(DishIngredient)
class DishIngredientAdmin(admin.ModelAdmin):
    list_display = (
        "dish",
        "food",
        "display_order",
    )
    list_filter = (
        "dish__category",
        "food__category",
    )
    search_fields = (
        "dish__name",
        "food__name",
    )
    autocomplete_fields = (
        "dish",
        "food",
    )
    ordering = (
        "dish",
        "display_order",
    )

class MealItemInline(admin.TabularInline):
    model = MealItem
    extra = 3
    autocomplete_fields = (
        "food",
        "dish",
    )
    fields = (
        "display_order",
        "item_type",
        "food",
        "dish",
        "amount",
        "unit",
        "reaction",
        "has_allergy_symptoms",
    )
    ordering = (
        "display_order",
        "id",
    )


@admin.register(Meal)
class MealAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "baby",
        "meal_number_display",
        "item_count",
        "updated_at",
    )
    list_filter = (
        "baby",
        "meal_number",
        "date",
    )
    search_fields = (
        "baby__name",
        "items__food__name",
        "items__dish__name",
    )
    date_hierarchy = "date"
    list_select_related = ("baby",)
    inlines = (MealItemInline,)
    ordering = (
        "-date",
        "meal_number",
    )

    @admin.display(
        description="食事",
        ordering="meal_number",
    )
    def meal_number_display(self, obj):
        return obj.get_meal_number_display()

    @admin.display(description="品数")
    def item_count(self, obj):
        return obj.items.count()


class MealItemIngredientInline(admin.TabularInline):
    model = MealItemIngredient
    extra = 0
    autocomplete_fields = ("food",)
    ordering = (
        "display_order",
        "id",
    )


@admin.register(MealItem)
class MealItemAdmin(admin.ModelAdmin):
    list_display = (
        "meal",
        "item_name_display",
        "item_type",
        "amount",
        "unit",
        "reaction",
        "has_allergy_symptoms",
    )
    list_filter = (
        "item_type",
        "unit",
        "reaction",
        "has_allergy_symptoms",
        "meal__date",
    )
    search_fields = (
        "food__name",
        "dish__name",
        "meal__baby__name",
    )
    autocomplete_fields = (
        "meal",
        "food",
        "dish",
    )
    list_select_related = (
        "meal",
        "meal__baby",
        "food",
        "dish",
    )
    inlines = (MealItemIngredientInline,)

    @admin.display(description="食材・料理")
    def item_name_display(self, obj):
        return obj.item_name


@admin.register(MealItemIngredient)
class MealItemIngredientAdmin(admin.ModelAdmin):
    list_display = (
        "meal_item",
        "food",
        "display_order",
    )
    list_filter = (
        "food__category",
    )
    search_fields = (
        "meal_item__food__name",
        "meal_item__dish__name",
        "food__name",
    )
    autocomplete_fields = (
        "meal_item",
        "food",
    )
    ordering = (
        "meal_item",
        "display_order",
    )

class AllergyReactionPhotoInline(admin.TabularInline):
    model = AllergyReactionPhoto
    extra = 0


@admin.register(AllergyReaction)
class AllergyReactionAdmin(admin.ModelAdmin):
    list_display = (
        "meal_item",
        "visited_doctor",
        "avoidance_instructed",
        "updated_at",
    )
    list_filter = (
        "visited_doctor",
        "avoidance_instructed",
    )
    search_fields = (
        "meal_item__food__name",
        "meal_item__dish__name",
        "doctor_diagnosis",
    )
    inlines = (AllergyReactionPhotoInline,)


@admin.register(AllergyReactionPhoto)
class AllergyReactionPhotoAdmin(admin.ModelAdmin):
    list_display = (
        "reaction",
        "created_at",
    )

@admin.register(FeedingGroup)
class FeedingGroupAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "display_order",
        "is_active",
    )
    list_editable = (
        "display_order",
        "is_active",
    )
    ordering = (
        "display_order",
        "name",
    )


@admin.register(FeedingGuideline)
class FeedingGuidelineAdmin(admin.ModelAdmin):
    list_display = (
        "age_range",
        "feeding_group",
        "minimum_amount",
        "maximum_amount",
        "unit",
        "food_form_note",
        "display_order",
    )
    list_filter = (
        "min_age_months",
        "feeding_group",
    )
    list_editable = (
        "display_order",
    )
    ordering = (
        "min_age_months",
        "display_order",
    )

    @admin.display(description="対象月齢")
    def age_range(self, obj):
        return (
            f"{obj.min_age_months}〜"
            f"{obj.max_age_months}か月"
        )