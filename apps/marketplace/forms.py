from django import forms
from django.forms import inlineformset_factory
from .models import Product, ProductImage
from .models import SavedPlace


class SavedPlaceForm(forms.ModelForm):
    class Meta:
        model = SavedPlace
        fields = ("name", "address_label", "notes", "latitude", "longitude")

        
class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = (
            "listing_type",
            "name",
            "brand",
            "size",
            "price",
            "image",
            "description",
            "usage_duration",
            "barter_reason",
            "barter_wanted",
            "location",
            "is_available",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "barter_wanted": forms.Textarea(attrs={"rows": 3}),
        }


ProductImageFormSet = inlineformset_factory(
    Product,
    ProductImage,
    fields=("image", "order"),
    extra=3,
    can_delete=True,
)
