from django.shortcuts import render
from .models import Product

def show_shop(request):
    products = Product.objects.all()
    context = {
        'products': products
    }
    return render(request, 'shop.html', context)