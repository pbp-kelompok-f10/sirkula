from django.shortcuts import render


def home(request):
    return render(request, "core/home.html")


def show_components(request):
    return render(request, "components.html")
