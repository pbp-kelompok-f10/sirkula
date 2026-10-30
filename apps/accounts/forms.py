import re

from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm

from .models import Profile

User = get_user_model()
MAX_AVATAR_BYTES = 2 * 1024 * 1024


def generate_internal_username(full_name):
    base = re.sub(r"[^A-Za-z0-9._-]+", "", (full_name or "").strip())
    base = base.strip("._-") or "user"
    base = base[:30]
    candidate = base
    suffix = 1
    while User.objects.filter(username__iexact=candidate).exists():
        candidate = f"{base}{suffix}"
        suffix += 1
    return candidate


class StyledFormMixin:

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput, forms.ClearableFileInput)):
                continue
            widget.attrs["class"] = (widget.attrs.get("class", "") + " a-input").strip()
            if not widget.attrs.get("placeholder") and isinstance(widget, forms.Select):
                widget.attrs["placeholder"] = "Pilih opsi"


# ---------- Auth ----------
class LoginForm(StyledFormMixin, AuthenticationForm):
    username = forms.CharField(
        label="Email",
        widget=forms.TextInput(
            attrs={
                "autocomplete": "email",
                "placeholder": "prabowo@sppg.ac.id",
            }
        ),
    )
    remember_me = forms.BooleanField(label="Ingat saya", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.pop("autofocus", None)

    def clean(self):
        cleaned_data = getattr(self, "cleaned_data", {}).copy()
        email = (self.data.get("username") or "").strip().lower()
        password = self.data.get("password") or ""

        if not email:
            self.add_error("username", "Email wajib diisi.")
        if not password:
            self.add_error("password", "Password wajib diisi.")
        if not email or not password:
            return cleaned_data

        user = User.objects.filter(email__iexact=email).order_by("pk").first()
        if user is None or not user.is_active or not user.check_password(password):
            self.add_error("username", "Email atau password yang Anda masukkan salah.")
            self.add_error("password", "Email atau password yang Anda masukkan salah.")
            return cleaned_data

        self.user_cache = user
        cleaned_data["username"] = email
        cleaned_data["password"] = password
        return cleaned_data


class RegisterStepOneForm(StyledFormMixin, forms.Form):
    username = forms.CharField(
        label="Nama lengkap",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Prabowo Subianto",
                "autocomplete": "name",
            }
        ),
    )
    email = forms.EmailField(
        label="Email",
        max_length=254,
        widget=forms.EmailInput(
            attrs={
                "placeholder": "prabowo@sppg.ac.id",
                "autocomplete": "email",
            }
        ),
    )
    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Konfirmasi password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def clean_username(self):
        full_name = (self.cleaned_data.get("username") or "").strip()
        if not full_name:
            raise forms.ValidationError("Nama lengkap wajib diisi.")
        if len(full_name) < 2:
            raise forms.ValidationError("Nama lengkap minimal 2 karakter.")
        return full_name

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Email ini sudah terdaftar.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Konfirmasi password tidak cocok.")
        if password1:
            full_name = cleaned_data.get("username", "")
            user = User(
                username=generate_internal_username(full_name),
                first_name=full_name,
                email=cleaned_data.get("email", ""),
            )
            try:
                password_validation.validate_password(password1, user=user)
            except forms.ValidationError as error:
                self.add_error("password1", error)
        return cleaned_data

    def save(self, commit=True):
        full_name = (self.cleaned_data.get("username") or "").strip()
        user = User(
            username=generate_internal_username(full_name),
            first_name=full_name,
            last_name="",
            email=self.cleaned_data["email"].strip().lower(),
        )
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class RegisterAddressForm(StyledFormMixin, forms.Form):
    address = forms.CharField(
        label="Alamat",
        max_length=200,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Jl. Istana Negara",
                "autocomplete": "street-address",
            }
        ),
    )
    map_choice = forms.ChoiceField(
        label="Map",
        choices=[
            ("", "Pilih lokasi"),
            ("Jl. Istana Negara", "Jl. Istana Negara"),
            ("Jl. Sudirman", "Jl. Sudirman"),
            ("Jl. Diponegoro", "Jl. Diponegoro"),
            ("Jl. Merdeka", "Jl. Merdeka"),
        ],
        required=False,
        widget=forms.Select(attrs={"placeholder": "Pilih lokasi"}),
    )


# ---------- Edit ----------
class ProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["display_name", "full_name", "bio", "location", "avatar"]
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 4}),
            "avatar": forms.ClearableFileInput(
                attrs={"accept": "image/*", "data-avatar-input": "true"}
            ),
        }

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if avatar and hasattr(avatar, "size") and avatar.size > MAX_AVATAR_BYTES:
            raise forms.ValidationError("Ukuran foto maksimal 2 MB.")
        return avatar

    def save(self, commit=True):
        # hapus file foto lama bila diganti / di-clear, agar tidak menumpuk di disk
        old = Profile.objects.get(pk=self.instance.pk).avatar if self.instance.pk else None
        profile = super().save(commit=commit)
        if commit and old and old.name != (profile.avatar.name if profile.avatar else ""):
            old.delete(save=False)
        return profile


class AccountForm(StyledFormMixin, forms.ModelForm):
    """Ubah username & email."""

    email = forms.EmailField(label="Email", max_length=254)

    class Meta:
        model = User
        fields = ["username", "email"]

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Email ini sudah dipakai akun lain.")
        return email


class DeleteAccountForm(StyledFormMixin, forms.Form):
    password = forms.CharField(
        label="Password", widget=forms.PasswordInput(attrs={"autocomplete": "current-password"})
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError("Password salah.")
        return password
