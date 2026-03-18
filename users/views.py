from django.shortcuts import render


def auth_page(request):
    return render(request, "users/index.html")
