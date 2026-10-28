from django.shortcuts import render

def home(request):
    return render(request, "index.html")

def show_components(request):
    return render(request, "components.html")