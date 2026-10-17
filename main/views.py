from django.shortcuts import render

# Create your views here.
def home(request):
    """Render the public Sirkula homepage."""
    return render(request, "homepage/home.html")
