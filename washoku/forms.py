import re

from django import forms

from .models import Comment, Feedback, Ingredient, MoodTag, Recipe


class CommentForm(forms.ModelForm):

    class Meta:
        model = Comment
        fields = ["kind", "body"]
        widgets = {
            "kind": forms.RadioSelect,
            "body": forms.Textarea(
                attrs={
                    "rows": 3,
                    "maxlength": 500,
                    "placeholder": "スイスで作るときの工夫や、食材の買い方など",
                }
            ),
        }


class CommentEditForm(forms.ModelForm):

    class Meta:
        model = Comment
        fields = ["body"]
        widgets = {
            "body": forms.Textarea(
                attrs={
                    "rows": 4,
                    "maxlength": 500,
                }
            ),
        }


class FeedbackForm(forms.ModelForm):

    # 人には見えない項目。全部の項目を埋めるボットだけが入力する。
    website = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "tabindex": "-1",
                "autocomplete": "off",
                "class": "washoku-trap",
                "aria-hidden": "true",
            }
        ),
    )

    class Meta:
        model = Feedback
        fields = ["message"]
        widgets = {
            "message": forms.Textarea(
                attrs={
                    "rows": 5,
                    "maxlength": 1000,
                    "placeholder": "ご自由にお書きください（1000文字まで）",
                }
            ),
        }

    def clean_message(self):

        message = self.cleaned_data["message"].strip()

        if not message:
            raise forms.ValidationError("内容を入力してください。")

        return message


class RecipeSubmissionForm(forms.ModelForm):
    """
    会員がレシピを投稿するフォーム。投稿は下書きになり、管理者が確認してから公開する。
    """

    ingredients_text = forms.CharField(
        label="材料",
        max_length=2000,
        help_text="1行に1つ。「食材名 分量」の形で書いてください（例: 鶏もも肉 300g）。",
        widget=forms.Textarea(
            attrs={
                "rows": 8,
                "placeholder": "鶏もも肉 300g\n醤油 大さじ2\nみりん 大さじ2",
            }
        ),
    )

    mood_tags = forms.ModelMultipleChoiceField(
        label="気分タグ",
        queryset=MoodTag.objects.order_by("display_order", "name"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Recipe
        fields = [
            "name",
            "category",
            "description",
            "cooking_time_minutes",
            "servings",
            "steps",
            "swiss_tips",
            "mood_tags",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "例: 鶏の照り焼き"}),
            "description": forms.TextInput(attrs={"placeholder": "どんな料理か、ひとことで"}),
            "cooking_time_minutes": forms.NumberInput(attrs={"min": 1, "max": 600, "inputmode": "numeric"}),
            "servings": forms.NumberInput(attrs={"min": 1, "max": 20, "inputmode": "numeric"}),
            "steps": forms.Textarea(
                attrs={
                    "rows": 8,
                    "maxlength": 4000,
                    "placeholder": "鶏肉の皮目をフォークで刺す\nフライパンで皮目から焼く\n…",
                }
            ),
            "swiss_tips": forms.Textarea(
                attrs={
                    "rows": 3,
                    "maxlength": 1000,
                    "placeholder": "どの店で何を買うか、代わりに使った食材など",
                }
            ),
        }
        help_texts = {
            "steps": "1行に1つの手順を書いてください。",
        }

    def clean_name(self):

        name = self.cleaned_data["name"].strip()

        if Recipe.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError("同じ名前のレシピがもうあります。少し違う名前にしてください。")

        return name

    def clean_ingredients_text(self):

        lines = split_lines(self.cleaned_data["ingredients_text"])

        if len(lines) < 2:
            raise forms.ValidationError("材料を2つ以上書いてください。")

        return "\n".join(lines)

    def clean_steps(self):

        lines = split_lines(self.cleaned_data["steps"])

        if not lines:
            raise forms.ValidationError("作り方を書いてください。")

        return "\n".join(lines)

    def parsed_ingredients(self):
        """
        材料の行を (食材, 分量) に分ける。食材リストにない材料は食材が None。
        """

        known = {}

        for ingredient in Ingredient.objects.all():
            for key in (ingredient.name, ingredient.name_de):
                if key:
                    known.setdefault(key.casefold(), ingredient)

        rows = []

        for line in self.cleaned_data["ingredients_text"].splitlines():
            name, amount = split_ingredient_line(line)
            rows.append((known.get(name.casefold()), name, amount))

        return rows


def split_lines(text):
    return [line.strip() for line in text.splitlines() if line.strip()]


def split_ingredient_line(line):
    """
    「鶏もも肉 300g」「鶏もも肉：300g」「鶏もも肉…300g」→ ("鶏もも肉", "300g")
    """

    line = line.strip().lstrip("・-*● ")

    parts = re.split(r"\s*[:：…]+\s*", line, maxsplit=1)

    if len(parts) == 1:
        parts = re.split(r"[\s\u3000]+", line)
        if len(parts) > 1:
            parts = [" ".join(parts[:-1]), parts[-1]]

    name = parts[0].strip()
    amount = parts[1].strip() if len(parts) > 1 else ""

    return name, amount
