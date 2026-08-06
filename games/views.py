from django.shortcuts import render


def game_list(request):
    return render(request, "games/index.html")


def block_breaker(request):
    return render(request, "games/block_breaker/index.html")