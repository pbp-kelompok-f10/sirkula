from django import forms

from .models import Category


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name"]
        labels = {
            "name": "Nama Kategori",
        }
        error_messages = {
            "name": {
                "required": "Nama kategori wajib diisi.",
                "max_length": "Nama kategori maksimal 100 karakter.",
            },
        }

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner

    def clean_name(self):
        name = self.cleaned_data["name"].strip()

        duplicates = Category.objects.filter(
            owner=self.owner,
            name__iexact=name,
        )

        if self.instance.pk:
            duplicates = duplicates.exclude(pk=self.instance.pk)

        if duplicates.exists():
            raise forms.ValidationError(
                "Kamu sudah memiliki kategori dengan nama ini."
            )
        return name