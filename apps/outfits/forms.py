from django import forms


class MixAndMatchPromptForm(forms.Form):
    prompt = forms.CharField(
        max_length=500,
        strip=True,
        error_messages={
            "required": "Tulis kebutuhan outfit terlebih dahulu.",
            "max_length": "Kebutuhan outfit maksimal 500 karakter.",
        },
    )
