from django import forms

from .models import SavedPlace


class SavedPlaceForm(forms.ModelForm):
    class Meta:
        model = SavedPlace
        fields = ("name", "address_label", "notes", "latitude", "longitude")

