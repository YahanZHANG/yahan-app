import re

from urllib.parse import urlparse

from django import forms

from .models import Comment, Feedback, Ingredient, MoodTag, Post, Recipe, Substitute


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


class PostForm(forms.ModelForm):
    """
    みんなの投稿 (コラム・おすすめ商品・参考リンク) のフォーム。
    商品のときだけ、お店・売り場・日本の何に近いかを聞く。
    参考リンクのときだけ、URL と出典を聞く (必須は URL だけ)。
    """

    # 同じ商品が Migros でも Coop でも買えることがあるので、お店は複数選べる
    shops = forms.MultipleChoiceField(
        label="買えるお店",
        choices=Post.SHOP_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text="買えるお店をすべて選んでください。",
    )

    class Meta:
        model = Post
        fields = ["url", "title", "source", "section", "resembles", "body"]
        widgets = {
            "title": forms.TextInput(attrs={"maxlength": 100}),
            "resembles": forms.TextInput(attrs={"placeholder": "例: 冷凍餃子、ちくわ"}),
            "body": forms.Textarea(attrs={"rows": 10, "maxlength": 4000}),
        }

    def __init__(self, *args, kind="column", **kwargs):

        super().__init__(*args, **kwargs)

        self.kind = kind

        if kind == "product":

            self.fields["title"].label = "商品名"
            self.fields["title"].widget.attrs["placeholder"] = "例: Migros の冷凍ギョーザ"
            self.fields["resembles"].help_text = ""
            self.fields["shops"].required = True
            self.order_fields(["title", "shops", "section", "resembles", "body"])
            self.fields["section"].choices = [("", "わからない")] + Post.SECTION_CHOICES
            self.fields["body"].label = "おすすめのポイント"
            self.fields["body"].widget.attrs["placeholder"] = (
                "味の感想、日本のものとの違い、おいしい食べ方、値段など"
            )

            for name in ("url", "source"):
                del self.fields[name]

        elif kind == "link":

            for name in ("shops", "section", "resembles"):
                del self.fields[name]

            self.fields["url"].required = True
            self.fields["url"].widget.attrs["placeholder"] = "https://"
            self.fields["title"].label = "記事のタイトル"
            self.fields["title"].required = False
            self.fields["source"].widget.attrs["placeholder"] = "例: スイス暮らしのブログ、2025年7月"
            self.fields["body"].label = "どんなことが書いてある？"
            self.fields["body"].required = False
            self.fields["body"].help_text = "記事の文章は写さずに、自分の言葉で短く。"
            self.fields["body"].widget.attrs["rows"] = 6
            self.fields["body"].widget.attrs["placeholder"] = (
                "例: Coop で買える日本の食材と、スイスの食材を使った和食のアレンジが載っています。"
            )

        else:

            for name in ("url", "source", "shops", "section", "resembles"):
                del self.fields[name]

            self.fields["title"].label = "タイトル"
            self.fields["title"].widget.attrs["placeholder"] = "例: 肉屋さんで薄切り肉を頼むコツ"
            self.fields["body"].widget.attrs["placeholder"] = (
                "スイスでの買い物や料理で、知っていると助かる経験を書いてください。"
            )

    def clean_title(self):

        title = self.cleaned_data["title"].strip()

        if not title and self.kind != "link":
            raise forms.ValidationError("入力してください。")

        return title

    def clean_body(self):

        body = self.cleaned_data["body"].strip()

        # 参考リンクは URL だけでよい (管理者があとでまとめる)
        if self.kind == "link" and not body:
            return body

        if len(body) < 10:
            raise forms.ValidationError("もう少し詳しく書いてください（10文字以上）。")

        return body

    def save(self, commit=True):

        post = super().save(commit=False)

        if "shops" in self.fields:
            post.shop = ",".join(self.cleaned_data["shops"])

        # タイトルがない参考リンクは、ひとまずサイト名を入れておく
        if self.kind == "link" and not post.title:
            post.title = urlparse(post.url).netloc or post.url[:100]

        if commit:
            post.save()

        return post


class SubstituteForm(forms.ModelForm):
    """
    会員が「日本の食材 → スイスで代わりに使えるもの」を教えるフォーム。
    スイスの食材は自由に書いてもらい、食材リストにある名前ならつなげる。
    """

    swiss_name = forms.CharField(
        label="スイスで買えるもの",
        max_length=100,
        widget=forms.TextInput(attrs={"placeholder": "例: Kohlrabi（コールラビ）"}),
    )

    class Meta:
        model = Substitute
        fields = ["original_name", "tips"]
        labels = {
            "original_name": "日本の食材",
            "tips": "使い方・コツ",
        }
        widgets = {
            "original_name": forms.TextInput(attrs={"placeholder": "例: かぶ"}),
            "tips": forms.Textarea(
                attrs={
                    "rows": 3,
                    "maxlength": 500,
                    "placeholder": "例: 薄めに切れば煮物や浅漬けにそのまま使える。",
                }
            ),
        }

    field_order = ["original_name", "swiss_name", "tips"]

    def clean_original_name(self):

        name = self.cleaned_data["original_name"].strip()

        if not name:
            raise forms.ValidationError("入力してください。")

        return name

    def clean(self):

        cleaned = super().clean()

        swiss_name = (cleaned.get("swiss_name") or "").strip()

        if not swiss_name:
            return cleaned

        # 食材リストの日本語名・ドイツ語名と同じなら、その食材につなぐ
        key = swiss_name.casefold()

        for ingredient in Ingredient.objects.all():
            names = [ingredient.name, *split_lines(ingredient.name_de.replace("/", "\n"))]
            if key in {name.strip().casefold() for name in names if name.strip()}:
                self.instance.substitute = ingredient
                self.instance.substitute_name = ""
                break
        else:
            self.instance.substitute = None
            self.instance.substitute_name = swiss_name

        original = cleaned.get("original_name")

        if original and Substitute.objects.filter(
            original_name=original,
            substitute=self.instance.substitute,
            substitute_name=self.instance.substitute_name,
        ).exists():
            raise forms.ValidationError("この組み合わせは、もう登録されています。")

        return cleaned


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
