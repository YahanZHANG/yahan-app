from django import forms

from .models import (
    NewsFeedback,
    NewsPreference,
    NewsSource,
    Region,
    Topic,
)


class NewsSettingsForm(forms.ModelForm):

    enabled_topics = forms.ModelMultipleChoiceField(
        queryset=Topic.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="表示するニューステーマ",
    )

    enabled_regions = forms.ModelMultipleChoiceField(
        queryset=Region.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="表示する地域",
    )

    enabled_sources = forms.ModelMultipleChoiceField(
        queryset=NewsSource.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="表示するニュースソース",
    )


    class Meta:

        model = NewsPreference

        fields = [
            "display_language",
            "font_size",
            "dark_mode",
        ]

        widgets = {
            "display_language":
                forms.RadioSelect,

            "font_size":
                forms.RadioSelect,

            "dark_mode": forms.CheckboxInput(
                attrs={
                    "class": "news-dark-checkbox",
                }
            ),
        }

        labels = {
            "display_language":
                "表示言語",

            "font_size":
                "文字サイズ",

             "dark_mode": "ダークモード",
        }


    def __init__(
        self,
        *args,
        **kwargs,
    ):

        super().__init__(
            *args,
            **kwargs,
        )


        # =====================================================
        # Active topics
        # =====================================================

        active_topics = (
            Topic.objects
            .filter(
                is_active=True
            )
            .order_by(
                "display_order",
                "name",
            )
        )


        # =====================================================
        # Active regions
        # =====================================================

        active_regions = (
            Region.objects
            .filter(
                is_active=True
            )
            .order_by(
                "display_order",
                "name",
            )
        )


        # =====================================================
        # Active sources
        # =====================================================

        active_sources = (
            NewsSource.objects
            .filter(
                is_active=True
            )
            .order_by(
                "display_order",
                "name",
            )
        )


        # =====================================================
        # Set querysets
        # =====================================================

        self.fields[
            "enabled_topics"
        ].queryset = active_topics

        self.fields[
            "enabled_regions"
        ].queryset = active_regions

        self.fields[
            "enabled_sources"
        ].queryset = active_sources


        # =====================================================
        # Initial selections
        #
        # hidden_* に入っていないものを
        # 「表示する項目」として初期選択する
        # =====================================================

        if (
            self.instance
            and self.instance.pk
        ):

            # Topics

            hidden_topic_ids = (
                self.instance
                .hidden_topics
                .values_list(
                    "id",
                    flat=True,
                )
            )

            self.fields[
                "enabled_topics"
            ].initial = (
                active_topics
                .exclude(
                    id__in=hidden_topic_ids
                )
            )


            # Regions

            hidden_region_ids = (
                self.instance
                .hidden_regions
                .values_list(
                    "id",
                    flat=True,
                )
            )

            self.fields[
                "enabled_regions"
            ].initial = (
                active_regions
                .exclude(
                    id__in=hidden_region_ids
                )
            )


            # Sources

            hidden_source_ids = (
                self.instance
                .hidden_sources
                .values_list(
                    "id",
                    flat=True,
                )
            )

            self.fields[
                "enabled_sources"
            ].initial = (
                active_sources
                .exclude(
                    id__in=hidden_source_ids
                )
            )


    def save(
        self,
        commit=True,
    ):

        preference = super().save(
            commit=commit
        )


        if commit:

            # =================================================
            # Topics
            # =================================================

            enabled_topics = self.cleaned_data[
                "enabled_topics"
            ]

            hidden_topics = (
                Topic.objects
                .filter(
                    is_active=True
                )
                .exclude(
                    id__in=enabled_topics.values_list(
                        "id",
                        flat=True,
                    )
                )
            )

            preference.hidden_topics.set(
                hidden_topics
            )


            # =================================================
            # Regions
            # =================================================

            enabled_regions = self.cleaned_data[
                "enabled_regions"
            ]

            hidden_regions = (
                Region.objects
                .filter(
                    is_active=True
                )
                .exclude(
                    id__in=enabled_regions.values_list(
                        "id",
                        flat=True,
                    )
                )
            )

            preference.hidden_regions.set(
                hidden_regions
            )


            # =================================================
            # Sources
            # =================================================

            enabled_sources = self.cleaned_data[
                "enabled_sources"
            ]

            hidden_sources = (
                NewsSource.objects
                .filter(
                    is_active=True
                )
                .exclude(
                    id__in=enabled_sources.values_list(
                        "id",
                        flat=True,
                    )
                )
            )

            preference.hidden_sources.set(
                hidden_sources
            )


        return preference


class NewsFeedbackForm(forms.ModelForm):

    class Meta:

        model = NewsFeedback

        fields = [
            "message",
        ]

        widgets = {
            "message":
                forms.Textarea(
                    attrs={
                        "class":
                            "news-feedback-textarea",

                        "placeholder":
                            "ご意見・ご要望を自由にお書きください",

                        "rows":
                            5,

                        "maxlength":
                            1000,
                    }
                ),
        }

        labels = {
            "message":
                "",
        }


from django import forms


class SupportContactForm(forms.Form):

    BANK_CHOICES = [
        (
            "ch",
            "スイスの銀行口座",
        ),
        (
            "jp",
            "日本の銀行口座",
        ),
    ]


    bank_country = forms.ChoiceField(
        label="希望する銀行口座",
        choices=BANK_CHOICES,
        required=False,
        widget=forms.RadioSelect,
    )


    name = forms.CharField(
        label="お名前（任意）",
        required=False,
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "news-support-input",
                "placeholder": "お名前",
                "autocomplete": "name",
            }
        ),
    )


    email = forms.EmailField(
        label="メールアドレス",
        max_length=254,
        widget=forms.EmailInput(
            attrs={
                "class": "news-support-input",
                "placeholder": "example@email.com",
                "autocomplete": "email",
            }
        ),
    )


    message = forms.CharField(
        label="応援方法・メッセージ",
        required=False,
        max_length=2000,
        widget=forms.Textarea(
            attrs={
                "class": "news-support-textarea",
                "placeholder": (
                    "どのような方法で応援したいか"
                    "教えてください。"
                ),
                "rows": 5,
            }
        ),
    )


    def __init__(
        self,
        *args,
        support_method=None,
        **kwargs,
    ):

        super().__init__(
            *args,
            **kwargs,
        )

        self.support_method = (
            support_method
        )


        # =============================================
        # Bank
        # =============================================

        if support_method == "bank":

            self.fields.pop(
                "message"
            )

            self.fields[
                "bank_country"
            ].required = True


        # =============================================
        # Other
        # =============================================

        else:

            self.fields.pop(
                "bank_country"
            )


    def clean(self):

        cleaned_data = (
            super().clean()
        )


        if (
            self.support_method
            == "other"
        ):

            message = (
                cleaned_data.get(
                    "message"
                )
                or ""
            ).strip()


            if not message:

                self.add_error(
                    "message",
                    (
                        "応援方法やメッセージを"
                        "入力してください。"
                    ),
                )


        return cleaned_data