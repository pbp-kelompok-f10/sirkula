from django import forms


class MixAndMatchPromptForm(forms.Form):
    prompt = forms.CharField(max_length=500, strip=True, error_messages={
        "required": "Tulis kebutuhan outfit terlebih dahulu.",
        "max_length": "Kebutuhan outfit maksimal 500 karakter.",
    })
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    recommendation = forms.ChoiceField(required=False, choices=[("", ""), ("best", "Terbaik"), ("random", "Acak")])


class ChatMessageForm(forms.Form):
    prompt = forms.CharField(max_length=500, strip=True, error_messages={
        "required": "Tulis pesan terlebih dahulu.",
        "max_length": "Pesan maksimal 500 karakter.",
    })
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
