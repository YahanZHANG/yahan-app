from django.contrib import admin

from .geocode import geocode_store
from .models import (
    Comment,
    CommentReport,
    Feedback,
    Household,
    HouseholdInvite,
    HouseholdMember,
    Ingredient,
    MoodTag,
    Notification,
    Post,
    Recipe,
    RecipeIngredient,
    RecipeRating,
    ShopType,
    Store,
    Substitute,
)


@admin.register(ShopType)
class ShopTypeAdmin(admin.ModelAdmin):
    list_display = (
        "rank",
        "name",
        "description",
    )

    ordering = (
        "rank",
    )


class SubstituteInline(admin.TabularInline):
    model = Substitute
    extra = 0


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "name_de",
        "category",
        "shop_list",
    )

    list_filter = (
        "category",
        "shops",
    )

    search_fields = (
        "name",
        "name_de",
        "name_fr",
        "search_group",
    )

    filter_horizontal = (
        "shops",
    )

    inlines = [
        SubstituteInline,
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("shops")

    @admin.display(description="買える店")
    def shop_list(self, obj):
        return "、".join(shop.name for shop in obj.shops.all())

    def save_related(self, request, form, formsets, change):

        super().save_related(request, form, formsets, change)

        # 買える店が変わると、この食材を使うレシピの「必要な店」も変わる
        for recipe in form.instance.recipes.all():
            recipe.update_shop_rank()


@admin.register(Substitute)
class SubstituteAdmin(admin.ModelAdmin):
    list_display = (
        "original_name",
        "substitute",
    )

    search_fields = (
        "original_name",
        "substitute__name",
    )

    autocomplete_fields = (
        "substitute",
    )


@admin.register(MoodTag)
class MoodTagAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "display_order",
    )

    ordering = (
        "display_order",
        "name",
    )


class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 0
    autocomplete_fields = (
        "ingredient",
    )


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "status",
        "origin",
        "submitted_by",
        "shop_rank_label",
        "updated_at",
    )

    list_filter = (
        "status",
        "category",
        "origin",
        "shop_rank",
        "mood_tags",
    )

    search_fields = (
        "name",
        "description",
    )

    filter_horizontal = (
        "mood_tags",
    )

    readonly_fields = (
        "submitted_by",
        "shop_rank_label",
        "created_at",
        "updated_at",
    )

    inlines = [
        RecipeIngredientInline,
    ]

    actions = [
        "publish",
        "unpublish",
    ]

    @admin.display(description="必要な店", ordering="shop_rank")
    def shop_rank_label(self, obj):

        if obj.shop_rank is None:
            return "未判定（店が未登録の材料あり）"

        shop = ShopType.objects.filter(rank=obj.shop_rank).first()

        return shop.name if shop else obj.shop_rank

    def save_related(self, request, form, formsets, change):

        super().save_related(request, form, formsets, change)

        form.instance.update_shop_rank()

    @admin.action(description="選んだレシピを公開する")
    def publish(self, request, queryset):
        updated = queryset.update(status="published")
        self.message_user(request, f"{updated}件を公開しました。")

    @admin.action(description="選んだレシピを下書きに戻す")
    def unpublish(self, request, queryset):
        updated = queryset.update(status="draft")
        self.message_user(request, f"{updated}件を下書きに戻しました。")


class HouseholdMemberInline(admin.TabularInline):
    model = HouseholdMember
    extra = 0


@admin.register(Household)
class HouseholdAdmin(admin.ModelAdmin):
    list_display = (
        "__str__",
        "created_at",
    )

    inlines = [
        HouseholdMemberInline,
    ]


@admin.register(HouseholdInvite)
class HouseholdInviteAdmin(admin.ModelAdmin):
    list_display = (
        "invited_by",
        "invited_user",
        "status",
        "created_at",
    )

    list_filter = (
        "status",
    )


@admin.register(RecipeRating)
class RecipeRatingAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "recipe",
        "rating",
        "updated_at",
    )

    list_filter = (
        "rating",
    )

    search_fields = (
        "user__username",
        "recipe__name",
    )


class CommentTargetFilter(admin.SimpleListFilter):
    title = "どこへのコメント"
    parameter_name = "target"

    def lookups(self, request, model_admin):
        return [
            ("recipe", "レシピ"),
            ("ingredient", "食材"),
            ("store", "お店"),
            ("post", "コラム・商品"),
        ]

    def queryset(self, request, queryset):
        if self.value() in ("recipe", "ingredient", "store", "post"):
            return queryset.filter(**{f"{self.value()}__isnull": False})
        return queryset


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "kind",
        "status",
        "shop",
        "author",
        "created_at",
    )

    list_filter = (
        "status",
        "kind",
        "shop",
        "section",
    )

    search_fields = (
        "title",
        "body",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    actions = [
        "publish",
        "unpublish",
    ]

    def save_model(self, request, obj, form, change):

        # 管理者が書いたものは author を自分にする
        if not change and obj.author_id is None:
            obj.author = request.user

        super().save_model(request, obj, form, change)

    @admin.action(description="選んだ投稿を公開する")
    def publish(self, request, queryset):
        queryset.update(status="published")

    @admin.action(description="選んだ投稿を確認待ちに戻す")
    def unpublish(self, request, queryset):
        queryset.update(status="draft")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = (
        "short_body",
        "target_label",
        "kind",
        "author",
        "report_count",
        "is_hidden",
        "admin_checked",
        "created_at",
    )

    list_filter = (
        "admin_checked",
        CommentTargetFilter,
        "is_hidden",
        "is_deleted",
        "kind",
    )

    list_editable = (
        "admin_checked",
    )

    search_fields = (
        "body",
        "author__username",
    )

    raw_id_fields = (
        "recipe",
        "ingredient",
        "store",
        "parent",
    )

    actions = [
        "mark_checked",
        "hide",
        "show",
    ]

    @admin.action(description="選んだコメントを確認済みにする")
    def mark_checked(self, request, queryset):
        updated = queryset.update(admin_checked=True)
        self.message_user(request, f"{updated}件を確認済みにしました。")

    @admin.display(description="本文")
    def short_body(self, obj):
        return obj.body[:40] or "（削除済み）"

    @admin.display(description="どこへ")
    def target_label(self, obj):
        if obj.recipe_id:
            kind = "レシピ"
        elif obj.store_id:
            kind = "お店"
        elif obj.post_id:
            kind = obj.post.get_kind_display()
        else:
            kind = "食材"
        return f"{kind}: {obj.target.name}"

    @admin.display(description="通報")
    def report_count(self, obj):
        return obj.reports.count()

    @admin.action(description="選んだコメントを非表示にする")
    def hide(self, request, queryset):
        queryset.update(is_hidden=True, admin_checked=True)

    @admin.action(description="選んだコメントを表示に戻す")
    def show(self, request, queryset):
        queryset.update(is_hidden=False, admin_checked=True)


@admin.register(CommentReport)
class CommentReportAdmin(admin.ModelAdmin):
    list_display = (
        "comment",
        "reporter",
        "reason",
        "created_at",
    )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "recipient",
        "actor",
        "comment",
        "is_read",
        "created_at",
    )


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "kind",
        "city",
        "area",
        "address",
        "has_location",
        "is_active",
    )

    list_filter = (
        "kind",
        "city",
        "is_active",
    )

    search_fields = (
        "name",
        "address",
        "area",
    )

    @admin.display(description="位置", boolean=True)
    def has_location(self, obj):
        return obj.latitude is not None

    def save_model(self, request, obj, form, change):

        # 住所を変えたのに緯度・経度を手で直していなければ、住所から調べ直す
        address_changed = "address" in form.changed_data
        location_edited = {"latitude", "longitude"} & set(form.changed_data)

        if (address_changed and not location_edited) or obj.latitude is None:
            if not geocode_store(obj, save=False):
                self.message_user(
                    request,
                    "住所から位置を調べられませんでした。距離順の並び替えでは最後に出ます。",
                    level="warning",
                )

        super().save_model(request, obj, form, change)


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = (
        "message",
        "created_at",
        "is_read",
    )

    list_filter = (
        "is_read",
    )

    list_editable = (
        "is_read",
    )
