from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.html import format_html

from .geocode import geocode_store
from .templatetags.washoku_tags import display_name
from .photos import commons_query, delete_uploaded_photos, find_commons_photo, upload_photo
from .models import (
    Announcement,
    Comment,
    CommentReport,
    DisplaySettings,
    Feedback,
    Household,
    HouseholdInvite,
    HouseholdMember,
    Ingredient,
    MemberPhoto,
    MoodTag,
    Notification,
    PollChoice,
    PollSuggestion,
    PollVote,
    Post,
    PushSubscription,
    Recipe,
    RecipeIngredient,
    RecipeRating,
    ShopType,
    Stamp,
    Store,
    Substitute,
)


def home_featured_ids(kind):
    # いまHOMEの「注目」に出ているもの (自動で入ったものを外すときの目印)
    from .views import featured_items

    return {entry["item"].pk for entry in featured_items() if entry["kind"] == kind}


class NarrowFeaturedOrderMixin:
    # 一覧で「注目の順番」の入力欄が場所を取らないように
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "featured_order":
            kwargs["widget"] = forms.NumberInput(attrs={"style": "width: 3.5em"})
        return super().formfield_for_dbfield(db_field, request, **kwargs)


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


class IngredientAdminForm(forms.ModelForm):

    photo_upload = forms.FileField(
        label="写真をアップロード",
        required=False,
        help_text="自分で撮った写真など。小さく変換して保存し、上の「写真」を置きかえます。",
        widget=forms.ClearableFileInput(attrs={"accept": "image/*"}),
    )

    class Meta:
        model = Ingredient
        fields = "__all__"

    def clean_photo_upload(self):

        photo = self.cleaned_data.get("photo_upload")

        if not photo:
            return ""

        try:
            return upload_photo(photo, "ingredients")
        except ValidationError as error:
            raise forms.ValidationError(error.messages)


class HasPhotoFilter(admin.SimpleListFilter):
    title = "写真"
    parameter_name = "photo"

    def lookups(self, request, model_admin):
        return [("yes", "あり"), ("no", "なし")]

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.exclude(photo_url="")
        if self.value() == "no":
            return queryset.filter(photo_url="")
        return queryset


# Wikimedia で一度に探す数 (1件に1〜2秒かかるので、画面がタイムアウトしない数に)
COMMONS_BATCH = 10


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    form = IngredientAdminForm

    list_display = (
        "name",
        "name_de",
        "category",
        "shop_list",
        "photo_thumb",
    )

    list_filter = (
        HasPhotoFilter,
        "category",
        "shops",
    )

    actions = [
        "find_photos_on_commons",
    ]

    @admin.display(description="写真")
    def photo_thumb(self, obj):
        if not obj.photo_url:
            return ""
        return format_html('<img src="{}" alt="" style="width:48px;height:48px;object-fit:cover;border-radius:6px">', obj.photo_url)

    def save_model(self, request, obj, form, change):

        uploaded = form.cleaned_data.get("photo_upload")

        if uploaded:
            obj.photo_url = uploaded
            obj.photo_credit = ""
            obj.photo_source = ""

        super().save_model(request, obj, form, change)

        # 管理画面で上げた写真も、ページの写真の一覧に入れる (前の写真は候補として残る)
        if uploaded:
            MemberPhoto.objects.create(ingredient=obj, url=uploaded, user=request.user)

    @admin.action(description="写真がない食材の写真を Wikimedia Commons で探す（10件ずつ）")
    def find_photos_on_commons(self, request, queryset):

        targets = list(queryset.filter(photo_url="")[:COMMONS_BATCH])
        found = []
        missing = []

        for ingredient in targets:

            try:
                photo = find_commons_photo(commons_query(ingredient))
            except Exception as error:  # 通信の失敗などで、ほかの食材まで止めない
                self.message_user(request, f"{ingredient.name}: 探せませんでした（{type(error).__name__}）", messages.WARNING)
                continue

            if not photo:
                missing.append(ingredient.name)
                continue

            ingredient.photo_url = photo["url"]
            ingredient.photo_credit = photo["credit"]
            ingredient.photo_source = photo["source"]
            ingredient.save(update_fields=["photo_url", "photo_credit", "photo_source"])
            found.append(ingredient.name)

        if found:
            self.message_user(request, f"写真を付けました（{len(found)}件）: {'、'.join(found)}。合っているか、食材のページで確かめてください。")
        if missing:
            self.message_user(request, f"見つかりませんでした: {'、'.join(missing)}", messages.WARNING)
        if not targets:
            self.message_user(request, "選んだ食材には、もう写真があります。", messages.INFO)

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
        "display_name",
        "status",
        "submitted_by",
        "created_at",
    )

    list_filter = (
        "status",
    )

    search_fields = (
        "original_name",
        "substitute__name",
        "substitute_name",
    )

    autocomplete_fields = (
        "substitute",
    )

    readonly_fields = (
        "submitted_by",
        "created_at",
    )

    actions = [
        "publish",
    ]

    @admin.display(description="スイスでの代用品")
    def display_name(self, obj):
        return obj.display_name

    @admin.action(description="選んだ代用品を公開する")
    def publish(self, request, queryset):
        queryset.update(status="published")


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = (
        "message",
        "link",
        "is_active",
        "created_at",
    )

    list_editable = (
        "is_active",
    )


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "created_at",
    )

    readonly_fields = (
        "user",
        "endpoint",
        "p256dh",
        "auth",
        "created_at",
    )

    def has_add_permission(self, request):
        return False


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


class PollChoiceInline(admin.TabularInline):
    """
    アンケートの選択肢 (種類が「アンケート」のときと、コラムにアンケートを付けるときに使う)。
    """

    model = PollChoice
    extra = 4
    fields = ("label", "order", "vote_count")
    readonly_fields = ("vote_count",)
    verbose_name = "選択肢（アンケートとコラムのとき）"
    verbose_name_plural = "選択肢（アンケート、またはコラムの最後に付けるアンケート。並び順の小さい順に出ます）"

    @admin.display(description="票数")
    def vote_count(self, obj):
        return obj.votes.count() if obj.pk else ""


class PollVoteInline(admin.TabularInline):
    """
    だれが何に投票したか (見るだけ)。
    """

    model = PollVote
    extra = 0
    can_delete = False
    fields = ("user_name", "choice_label", "voted_time")
    readonly_fields = ("user_name", "choice_label", "voted_time")
    ordering = ("-voted_at",)
    verbose_name = "回答"
    verbose_name_plural = "回答した人（新しい順）"

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="回答した人")
    def user_name(self, obj):
        if obj.user is None:
            return "ゲスト（ログインなし）"
        return f"{display_name(obj.user)}（{obj.user.username}）"

    @admin.display(description="選んだ答え")
    def choice_label(self, obj):
        return obj.choice.label

    @admin.display(description="回答日時")
    def voted_time(self, obj):
        return timezone.localtime(obj.voted_at).strftime("%Y/%m/%d %H:%M")


@admin.register(PollVote)
class PollVoteAdmin(admin.ModelAdmin):
    """
    アンケートの回答の一覧。アンケートや選択肢で絞り込める。
    """

    list_display = ("poll_name", "choice_label", "user_name", "voted_time")
    list_filter = (("post", admin.RelatedOnlyFieldListFilter),)
    list_select_related = ("post", "choice", "user")
    search_fields = ("user__username", "post__title", "choice__label")
    readonly_fields = ("post", "choice", "user", "voted_at")

    def has_add_permission(self, request):
        return False

    @admin.display(description="アンケート", ordering="post__title")
    def poll_name(self, obj):
        return obj.post.poll_title

    @admin.display(description="選んだ答え", ordering="choice__order")
    def choice_label(self, obj):
        return obj.choice.label

    @admin.display(description="回答した人", ordering="user__username")
    def user_name(self, obj):
        if obj.user is None:
            return "ゲスト（ログインなし）"
        return f"{display_name(obj.user)}（{obj.user.username}）"

    @admin.display(description="回答日時", ordering="voted_at")
    def voted_time(self, obj):
        return timezone.localtime(obj.voted_at).strftime("%Y/%m/%d %H:%M")


class HomePhotoAdminForm(forms.ModelForm):
    """注目・質問の HOME カードに出す写真を、管理画面からアップロードできるようにする。"""

    home_photo_upload = forms.FileField(
        label="HOMEの写真をアップロード",
        required=False,
        help_text="小さく変換して保存し、上の「HOMEの写真」を置きかえます。消すときは「HOMEの写真」を空にします。",
        widget=forms.ClearableFileInput(attrs={"accept": "image/*"}),
    )

    def clean_home_photo_upload(self):

        photo = self.cleaned_data.get("home_photo_upload")

        if not photo:
            return ""

        try:
            return upload_photo(photo, "home")
        except ValidationError as error:
            raise forms.ValidationError(error.messages)


class HomePhotoAdminMixin:
    """HOMEの写真のアップロードとプレビュー。"""

    @admin.display(description="HOMEの写真（いま）")
    def home_photo_preview(self, obj):
        if not obj.home_photo_url:
            return "なし（文字だけ）"
        return format_html('<img src="{}" alt="" style="width:160px;max-height:120px;object-fit:cover;border-radius:8px">', obj.home_photo_url)

    def save_model(self, request, obj, form, change):
        uploaded = form.cleaned_data.get("home_photo_upload")
        if uploaded:
            obj.home_photo_url = uploaded
        super().save_model(request, obj, form, change)


class PostAdminForm(HomePhotoAdminForm):
    class Meta:
        model = Post
        fields = "__all__"


class CommentAdminForm(HomePhotoAdminForm):
    class Meta:
        model = Comment
        fields = "__all__"


@admin.register(Post)
class PostAdmin(HomePhotoAdminMixin, NarrowFeaturedOrderMixin, admin.ModelAdmin):
    form = PostAdminForm
    inlines = (
        PollChoiceInline,
        PollVoteInline,
    )

    list_display = (
        "title",
        "kind",
        "status",
        "is_featured",
        "featured_order",
        "featured_hidden",
        "on_home",
        "publish_at",
        "shop_names",
        "author",
        "created_at",
    )

    list_filter = (
        "status",
        "kind",
        "is_featured",
        "featured_hidden",
        "section",
    )

    list_editable = (
        "is_featured",
        "featured_order",
        "featured_hidden",
    )

    search_fields = (
        "title",
        "body",
    )

    autocomplete_fields = (
        "ingredients",
    )

    def changelist_view(self, request, extra_context=None):
        self._home_featured = home_featured_ids("post")
        return super().changelist_view(request, extra_context)

    @admin.display(description="いまHOMEの注目", boolean=True)
    def on_home(self, obj):
        return obj.pk in getattr(self, "_home_featured", set())

    @admin.display(description="買えるお店")
    def shop_names(self, obj):
        return "、".join(obj.shop_labels())

    readonly_fields = (
        "updated_at",
        "home_photo_preview",
    )

    actions = [
        "publish",
        "unpublish",
        "feature",
        "unfeature",
    ]

    def save_model(self, request, obj, form, change):

        # 管理者が書いたものは author を自分にする
        if not change and obj.author_id is None:
            obj.author = request.user

        # 確認待ちから公開にしたら、一覧の一番上に来るよう投稿日時を今にする (日時を自分で変えたときはそのまま)
        if (
            change
            and obj.status == "published"
            and form.initial.get("status") == "draft"
            and "created_at" not in form.changed_data
        ):
            obj.created_at = timezone.now()

        super().save_model(request, obj, form, change)

    @admin.action(description="選んだ投稿を公開する")
    def publish(self, request, queryset):
        queryset.filter(status="draft").update(status="published", created_at=timezone.now())

    @admin.action(description="選んだ投稿を確認待ちに戻す")
    def unpublish(self, request, queryset):
        queryset.update(status="draft")

    @admin.action(description="選んだ投稿をHOMEの注目に出す")
    def feature(self, request, queryset):
        queryset.update(is_featured=True)

    @admin.action(description="選んだ投稿をHOMEの注目から外す")
    def unfeature(self, request, queryset):
        queryset.update(is_featured=False)


@admin.register(Comment)
class CommentAdmin(HomePhotoAdminMixin, NarrowFeaturedOrderMixin, admin.ModelAdmin):
    form = CommentAdminForm
    readonly_fields = (
        "home_photo_preview",
    )

    list_display = (
        "short_body",
        "target_label",
        "kind",
        "author",
        "report_count",
        "is_hidden",
        "is_featured",
        "featured_order",
        "featured_hidden",
        "on_home",
        "reopened",
        "home_hidden",
        "home_until",
        "admin_checked",
        "created_at",
    )

    list_filter = (
        "admin_checked",
        CommentTargetFilter,
        "is_hidden",
        "is_deleted",
        "is_featured",
        "featured_hidden",
        "reopened",
        "home_hidden",
        "kind",
    )

    list_editable = (
        "is_featured",
        "featured_order",
        "featured_hidden",
        "reopened",
        "home_hidden",
        "home_until",
        "admin_checked",
    )

    def changelist_view(self, request, extra_context=None):
        self._home_featured = home_featured_ids("comment")
        return super().changelist_view(request, extra_context)

    @admin.display(description="いまHOMEの注目", boolean=True)
    def on_home(self, obj):
        return obj.pk in getattr(self, "_home_featured", set())

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


@admin.register(MemberPhoto)
class MemberPhotoAdmin(admin.ModelAdmin):
    """
    投稿された写真の一覧。載せる写真を選ぶのは、料理・食材のページで。
    """

    list_display = (
        "photo_thumb",
        "target",
        "user",
        "is_shown",
        "admin_checked",
        "created_at",
    )

    list_editable = ("admin_checked",)
    list_filter = ("admin_checked",)
    list_select_related = ("recipe", "ingredient", "user")
    readonly_fields = ("recipe", "ingredient", "url", "user", "created_at")

    def has_add_permission(self, request):
        return False

    @admin.display(description="写真")
    def photo_thumb(self, obj):
        return format_html('<img src="{}" alt="" style="width:64px;height:64px;object-fit:cover;border-radius:6px">', obj.url)

    @admin.display(description="掲載中", boolean=True)
    def is_shown(self, obj):
        return obj.is_shown

    def delete_model(self, request, obj):
        self.delete_queryset(request, MemberPhoto.objects.filter(pk=obj.pk))

    def delete_queryset(self, request, queryset):
        # 載っている写真なら、ページからも外す
        for photo in queryset.select_related("recipe", "ingredient"):
            if photo.is_shown:
                photo.target.__class__.objects.filter(pk=photo.target.pk).update(**{photo.target_field: ""})
            delete_uploaded_photos(photo.url)
        queryset.delete()


@admin.register(PollSuggestion)
class PollSuggestionAdmin(admin.ModelAdmin):
    """
    みんなからのアンケートの提案。「アンケートの下書きを作る」で下書きにしてから、
    文や選択肢を整えて公開する。
    """

    list_display = ("question", "status", "suggested_by", "created_at", "poll")
    list_filter = ("status",)
    search_fields = ("question", "choices", "note")
    readonly_fields = ("user", "created_at", "poll")
    fields = ("question", "choices", "note", "status", "user", "created_at", "poll")
    actions = ("make_draft_polls", "mark_declined")

    @admin.display(description="提案した人")
    def suggested_by(self, obj):
        return display_name(obj.user) if obj.user else "ゲスト"

    @admin.action(description="アンケートの下書きを作る")
    def make_draft_polls(self, request, queryset):

        made = 0

        for suggestion in queryset.filter(poll__isnull=True):

            poll = Post.objects.create(
                kind="poll",
                title=suggestion.question,
                body=suggestion.note,
                status="draft",
                author=request.user,
            )

            for order, label in enumerate(suggestion.choice_lines(), start=1):
                PollChoice.objects.create(post=poll, label=label, order=order)

            suggestion.poll = poll
            suggestion.status = "adopted"
            suggestion.save(update_fields=["poll", "status"])
            made += 1

        self.message_user(
            request,
            f"{made}件のアンケートを下書きで作りました。「みんなの投稿」で文と選択肢を整えて公開してください。",
            messages.SUCCESS,
        )

    @admin.action(description="見送りにする")
    def mark_declined(self, request, queryset):
        queryset.update(status="declined")


@admin.register(DisplaySettings)
class DisplaySettingsAdmin(admin.ModelAdmin):
    """
    1件だけの設定。一覧を開くとすぐその設定の画面になる。
    """

    fieldsets = (
        ("HOMEに出すもの", {
            "fields": (
                "home_featured_show_stamps",
            ),
        }),
        ("コラム一覧（/washoku/columns/）に出すもの", {
            "fields": (
                "column_show_sort",
                "column_show_author",
                "column_show_date",
                "column_show_time",
                "column_show_comments",
                "column_show_stamps",
                "column_show_readers",
            ),
        }),
    )

    def changelist_view(self, request, extra_context=None):
        settings_row = DisplaySettings.load()
        return redirect("admin:washoku_displaysettings_change", settings_row.pk)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Stamp)
class StampAdmin(admin.ModelAdmin):
    list_display = ("key", "emoji", "label", "order", "is_active")
    list_display_links = ("key",)
    list_editable = ("emoji", "label", "order", "is_active")

    def get_readonly_fields(self, request, obj=None):
        # 押された記録が key でつながっているので、作ったあとは変えない
        return ("key",) if obj else ()

    def has_delete_permission(self, request, obj=None):
        # 消すと押されたぶんが表示できなくなるので「表示する」を外して隠す
        return False
