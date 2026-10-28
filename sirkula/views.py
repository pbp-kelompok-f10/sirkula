from django.shortcuts import render

def show_shop(request):
    products = []  # atau kirim queryset Product jika model sudah siap
    context = {
        'products': products
    }
    return render(request, 'shop.html', context)