from django import forms
from .models import Category, WardrobeItem
from .validators import validate_photo_size
from django.core.validators import FileExtensionValidator


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


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    widget = MultipleImageInput

    def clean(self, data, initial=None):
        if not data:
            raise forms.ValidationError(
                "Tambahkan minimal satu foto pakaian."
            )

        files = list(data) if isinstance(data, (list, tuple)) else [data]

        if len(files) > 5:
            raise forms.ValidationError(
                "Maksimal lima foto untuk setiap pakaian."
            )

        clean_single_image = super().clean
        cleaned_files = []

        for uploaded_file in files:
            validate_photo_size(uploaded_file)
            image = clean_single_image(uploaded_file, initial)

            if image.image.format not in {"JPEG", "PNG", "WEBP"}:
                raise forms.ValidationError(
                    "Format foto harus JPG, PNG, atau WebP."
                )

            cleaned_files.append(image)

        return cleaned_files


class WardrobeItemForm(forms.ModelForm):
    name = forms.CharField(
        label="Nama Pakaian",
        max_length=100,
        error_messages={
            "required": "Nama pakaian wajib diisi.",
            "max_length": "Nama pakaian maksimal 100 karakter.",
        },
    )
    photos = MultipleImageField(
        label="Foto Pakaian",
        validators=[
            FileExtensionValidator(
                allowed_extensions=["jpg", "jpeg", "png", "webp"]
            )
        ],
        error_messages={
            "invalid_image": "File harus berupa gambar yang valid.",
        },
        widget=MultipleImageInput(attrs={
            "accept": "image/jpeg,image/png,image/webp",
        }),
    )

    class Meta:
        model = WardrobeItem
        fields = ["name", "category", "photos"]
        labels = {
            "category": "Kategori",
        }

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["category"].required = True
        self.fields["category"].empty_label = "Pilih kategori"
        self.fields["category"].error_messages.update({
            "required": "Kategori wajib dipilih.",
            "invalid_choice": "Pilih kategori milik akunmu.",
        })

        if owner is not None and owner.is_authenticated:
            self.fields["category"].queryset = Category.objects.filter(
                owner=owner
            )
        else:
            self.fields["category"].queryset = Category.objects.none()