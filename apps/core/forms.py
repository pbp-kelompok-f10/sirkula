from django import forms

from .models import Review


class ReviewForm(forms.ModelForm):
    content = forms.CharField(
        label="Ulasanmu",
        min_length=10,
        max_length=1000,
        strip=True,
        widget=forms.Textarea(attrs={
            "class": "textarea textarea-bordered w-full min-h-36 bg-base-100 text-base-content",
            "rows": 5,
            "placeholder": "Ceritakan pengalamanmu menggunakan Sirkula…",
            "aria-describedby": "review-help review-errors",
        }),
        error_messages={
            "required": "Tulis ulasanmu terlebih dahulu.",
            "min_length": "Ulasan minimal 10 karakter.",
            "max_length": "Ulasan maksimal 1.000 karakter.",
        },
    )

    class Meta:
        model = Review
        fields = ["content"]
