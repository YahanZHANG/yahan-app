from django.shortcuts import render

from .models import (
    Ingredient,
    Recipe,
)


def home(request):
    """
    公開までは準備中のページ。管理者にはデータの件数を見せる。
    """

    context = {}

    if request.user.is_staff:
        context.update(
            {
                "published_count": Recipe.objects.filter(status="published").count(),
                "draft_count": Recipe.objects.filter(status="draft").count(),
                "ingredient_count": Ingredient.objects.count(),
            }
        )

    return render(
        request,
        "washoku/home.html",
        context,
    )
