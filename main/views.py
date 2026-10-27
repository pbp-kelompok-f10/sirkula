from django.shortcuts import render

# Create your views here.
def wardrobe(request):
    return render(request, "wardrobe.html")