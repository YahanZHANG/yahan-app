from django import forms

from .models import NewsPreference, Topic


class NewsSettingsForm(forms.ModelForm):
    enabled_topics = forms.ModelMultipleChoiceField(
        queryset=Topic.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="表示するテーマ",
    )

    class Meta:
        model = NewsPreference

        fields = [
            "display_language",
            "font_size",
        ]

        widgets = {
            "display_language": forms.RadioSelect,
            "font_size": forms.RadioSelect,
        }

        labels = {
            "display_language": "表示言語",
            "font_size": "文字サイズ",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        active_topics = Topic.objects.filter(
            is_active=True
        )

        self.fields[
            "enabled_topics"
        ].queryset = active_topics

        if self.instance and self.instance.pk:
            hidden_ids = self.instance.hidden_topics.values_list(
                "id",
                flat=True,
            )

            self.fields[
                "enabled_topics"
            ].initial = active_topics.exclude(
                id__in=hidden_ids
            )

    def save(self, commit=True):
        preference = super().save(
            commit=commit
        )

        if commit:
            enabled_topics = self.cleaned_data[
                "enabled_topics"
            ]

            hidden_topics = Topic.objects.filter(
                is_active=True
            ).exclude(
                id__in=enabled_topics.values_list(
                    "id",
                    flat=True,
                )
            )

            preference.hidden_topics.set(
                hidden_topics
            )

        return preference