from django import forms
from .models import Category, WardrobeItem, WardrobeItemImage
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
            if self.required:
                raise forms.ValidationError(
                    "Tambahkan minimal satu foto pakaian."
                )
            return []

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

class WardrobeItemEditForm(WardrobeItemForm):
    delete_photos = forms.ModelMultipleChoiceField(
        label="Foto yang dihapus",
        queryset=WardrobeItemImage.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        error_messages={
            "invalid_choice": (
                "Pilih foto yang memang milik pakaian ini."
            ),
            "invalid_pk_value": (
                "Pilihan foto tidak valid."
            ),
        },
    )

    class Meta(WardrobeItemForm.Meta):
        fields = ["name", "category", "photos", "delete_photos"]

    def __init__(self, *args, owner, instance, **kwargs):
        if instance.pk is None:
            raise ValueError(
                "Form edit memerlukan pakaian yang sudah tersimpan."
            )

        if (
            owner is None
            or not owner.is_authenticated
            or instance.owner_id != owner.pk
        ):
            raise ValueError(
                "Form edit hanya boleh digunakan oleh pemilik pakaian."
            )

        super().__init__(
            *args,
            owner=owner,
            instance=instance,
            **kwargs,
        )

        self.fields["photos"].required = False
        self.fields["photos"].label = "Foto Baru"

        self.fields["delete_photos"].queryset = (
            instance.images.all()
        )

    def clean(self):
        cleaned_data = super().clean()

        # Jangan menghitung jumlah akhir jika pilihan foto
        # atau unggahan baru sudah gagal divalidasi.
        if (
            "photos" not in cleaned_data
            or "delete_photos" not in cleaned_data
        ):
            return cleaned_data

        new_photos = cleaned_data["photos"]
        deleted_photos = cleaned_data["delete_photos"]

        existing_count = self.instance.images.count()
        remaining_count = existing_count - deleted_photos.count()
        final_count = remaining_count + len(new_photos)

        if final_count < 1:
            self.add_error(
                "photos",
                "Pakaian harus memiliki minimal satu foto "
                "setelah perubahan.",
            )
        elif final_count > 5:
            self.add_error(
                "photos",
                "Total foto lama dan foto baru maksimal lima. "
                "Hapus beberapa foto lama atau kurangi foto baru.",
            )

        return cleaned_data

class WardrobeItemDraftForm(WardrobeItemForm):
    delete_photos = forms.ModelMultipleChoiceField(
        label="Foto yang dihapus",
        queryset=WardrobeItemImage.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        error_messages={
            "invalid_choice": (
                "Pilih foto yang memang milik draft ini."
            ),
            "invalid_pk_value": "Pilihan foto tidak valid.",
        },
    )

    class Meta(WardrobeItemForm.Meta):
        fields = ["name", "category", "photos", "delete_photos"]

    def __init__(self, *args, owner, instance=None, **kwargs):
        if owner is None or not owner.is_authenticated:
            raise ValueError(
                "Form draft memerlukan pengguna yang sudah login."
            )

        if instance is not None and instance.pk is not None:
            if (
                instance.owner_id != owner.pk
                or instance.status != WardrobeItem.Status.DRAFT
            ):
                raise ValueError(
                    "Form ini hanya boleh membuka draft milik pengguna."
                )

        super().__init__(
            *args,
            owner=owner,
            instance=instance,
            **kwargs,
        )

        self.instance.owner = owner
        self.instance.status = WardrobeItem.Status.DRAFT

        self.fields["name"].required = False
        self.fields["category"].required = False
        self.fields["photos"].required = False
        self.fields["photos"].label = "Foto Baru"

        if self.instance.pk is not None:
            self.fields["delete_photos"].queryset = (
                self.instance.images.all()
            )

    def clean(self):
        cleaned_data = super().clean()

        required_keys = (
            "name",
            "category",
            "photos",
            "delete_photos",
        )

        if any(
            key not in cleaned_data
            for key in required_keys
        ):
            return cleaned_data

        existing_count = (
            self.instance.images.count()
            if self.instance.pk is not None
            else 0
        )

        deleted_count = (
            cleaned_data["delete_photos"].count()
        )
        new_count = len(cleaned_data["photos"])

        final_count = (
            existing_count - deleted_count + new_count
        )

        if final_count > 5:
            self.add_error(
                "photos",
                "Total foto lama dan foto baru maksimal lima.",
            )

        has_content = (
            bool(cleaned_data["name"])
            or cleaned_data["category"] is not None
            or final_count > 0
        )

        if not has_content:
            self.add_error(
                None,
                "Isi minimal nama, kategori, atau satu foto "
                "sebelum menyimpan draft.",
            )

        return cleaned_data


class WardrobeItemDraftCompleteForm(WardrobeItemDraftForm):
    def __init__(self, *args, owner, instance, **kwargs):
        if instance is None or instance.pk is None:
            raise ValueError(
                "Penyelesaian memerlukan draft yang sudah tersimpan."
            )

        super().__init__(
            *args,
            owner=owner,
            instance=instance,
            **kwargs,
        )

        self.fields["name"].required = True
        self.fields["category"].required = True

    def clean(self):
        cleaned_data = super().clean()

        if (
            "photos" not in cleaned_data
            or "delete_photos" not in cleaned_data
        ):
            return cleaned_data

        remaining_count = (
            self.instance.images.count()
            - cleaned_data["delete_photos"].count()
        )
        final_count = (
            remaining_count
            + len(cleaned_data["photos"])
        )

        if final_count < 1:
            self.add_error(
                "photos",
                "Tambahkan minimal satu foto pakaian.",
            )

        return cleaned_data
