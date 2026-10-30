from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.hashers import make_password
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_safe
from django.views.decorators.cache import never_cache
from django.views.decorators.vary import vary_on_cookie

from apps.bartering.models import BarterOffer
from apps.wardrobe.models import WardrobeItem
from apps.wardrobe.views import _wardrobe_context

from .forms import (
    AccountForm,
    DeleteAccountForm,
    LoginForm,
    ProfileForm,
    RegisterAddressForm,
    RegisterStepOneForm,
)
from .models import Profile

User = get_user_model()
REGISTER_SESSION_KEY = "pending_registration"


def get_profile(user):
    """Ambil profil; buat bila belum ada (mis. user lama sebelum signal dipasang)."""
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


def _settings_context(active, **extra):
    return {"show_settings_nav": True, "active": active, **extra}


# ---------- Auth ----------
class SirkulaLoginView(LoginView):
    template_name = "login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "title": "Masuk",
            "subtitle": "Selamat datang kembali di Sirkula.",
            "submit_label": "Masuk",
            "footer_text": "Belum punya akun?",
            "footer_link": "Daftar",
            "footer_url": reverse_lazy("accounts:register"),
        })
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        if not form.cleaned_data.get("remember_me"):
            self.request.session.set_expiry(0)
        messages.success(self.request, f"Halo, {get_profile(form.get_user()).name}!")
        return response

    def get_success_url(self):
        redirect_to = self.request.POST.get("next") or self.request.GET.get("next") or ""
        if redirect_to and url_has_allowed_host_and_scheme(redirect_to, allowed_hosts={self.request.get_host()}):
            return redirect_to
        return reverse("accounts:me")


def _clear_pending_registration(request):
    if REGISTER_SESSION_KEY in request.session:
        del request.session[REGISTER_SESSION_KEY]


def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:me")

    if request.method == "POST":
        form = RegisterStepOneForm(request.POST)
        if form.is_valid():
            request.session[REGISTER_SESSION_KEY] = {
                "full_name": form.cleaned_data["username"].strip(),
                "email": form.cleaned_data["email"].strip().lower(),
                "password_hash": make_password(form.cleaned_data["password1"]),
            }
            return redirect("accounts:register_location")
        return render(request, "accounts/register.html", {"form": form, "step": 1})

    return render(request, "accounts/register.html", {"form": RegisterStepOneForm(), "step": 1})


def register_location(request):
    if request.user.is_authenticated:
        return redirect("accounts:me")

    pending = request.session.get(REGISTER_SESSION_KEY)
    if not pending or not pending.get("password_hash"):
        _clear_pending_registration(request)
        messages.warning(request, "Silakan lengkapi data akun terlebih dahulu.")
        return redirect("accounts:register")

    form = RegisterAddressForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if User.objects.filter(email__iexact=pending["email"]).exists():
            _clear_pending_registration(request)
            messages.error(request, "Email ini sudah terdaftar. Silakan masuk atau gunakan email lain.")
            return redirect("accounts:register")

        full_name = pending["full_name"]
        candidate = "".join(ch for ch in full_name if ch.isalnum() or ch in "._-") or "user"
        candidate = candidate[:30].strip("._-") or "user"
        suffix = 1
        while True:
            final_username = candidate if suffix == 1 else f"{candidate}{suffix}"
            if not User.objects.filter(username__iexact=final_username).exists():
                break
            suffix += 1

        user = User(
            username=final_username,
            email=pending["email"],
            first_name=full_name,
            last_name="",
        )
        user.password = pending["password_hash"]
        user.save()

        profile = get_profile(user)
        profile.display_name = full_name
        profile.full_name = full_name
        profile.location = form.cleaned_data.get("address") or form.cleaned_data.get("map_choice") or ""
        profile.save()
        _clear_pending_registration(request)
        messages.success(request, "Akun berhasil dibuat, silakan login untuk masuk.")
        return redirect("accounts:login")
    return render(request, "accounts/register_location.html", {
        "form": form,
        "step": 2,
        "pending_user": pending,
    })

@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, "Kamu sudah keluar.")
    return redirect("core:home")


# ---------- Profil ----------
@login_required
def my_profile(request):
    return redirect("accounts:profile", username=request.user.username)


@never_cache
@vary_on_cookie
def profile_detail(request, username):
    user = get_object_or_404(User, username=username)
    profile = get_profile(user)
    is_owner = request.user == user
    wardrobe_items = WardrobeItem.objects.none()
    if is_owner:
        wardrobe_items = list(
            WardrobeItem.objects.filter(owner=user, status=WardrobeItem.Status.ACTIVE)
            .select_related("category").prefetch_related("images")
        )
    return render(request, "profile.html", {
        "profile": profile,
        "is_owner": is_owner,
        "profile_user": user,
        "wardrobe_items": wardrobe_items,
        "wardrobe_count": len(wardrobe_items) if is_owner else None,
        "active_barter_count": BarterOffer.objects.filter(
            Q(proposer=user) | Q(recipient=user),
            status__in=[BarterOffer.Status.PENDING, BarterOffer.Status.ACCEPTED,
                        BarterOffer.Status.SHIPPING],
        ).count() if is_owner else None,
        "completed_barter_count": BarterOffer.objects.filter(
            Q(proposer=user) | Q(recipient=user), status=BarterOffer.Status.COMPLETED,
        ).count(),
    })


@login_required
@never_cache
@require_safe
def add_wardrobe_item(request):
    """Open the existing draft-aware wardrobe form; saving stays in wardrobe."""
    context = _wardrobe_context(request)
    context["open_item_modal"] = True
    return render(request, "wardrobe/index.html", context)


@login_required
def profile_edit(request):
    form = ProfileForm(request.POST or None, request.FILES or None,
                       instance=get_profile(request.user))
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profil berhasil diperbarui.")
        return redirect("accounts:profile", username=request.user.username)
    return render(request, "profile_edit.html", {
        "form": form,
        "title": "Edit Profil",
        "subtitle": "Perbarui informasi yang tampil di profilmu.",
        "submit_label": "Simpan",
        "cancel_url": reverse("accounts:me"),
        **_settings_context("profile"),
    })


@login_required
def account_edit(request):
    form = AccountForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Data akun berhasil diperbarui.")
        return redirect("accounts:account_edit")
    return render(request, "accounts/form_page.html", {
        "form": form,
        "title": "Pengaturan Akun",
        "subtitle": "Ubah username dan email. Username juga menjadi alamat profilmu.",
        "submit_label": "Simpan",
        **_settings_context("account"),
    })


class PasswordChangeViewStyled(PasswordChangeView):
    template_name = "accounts/form_page.html"
    success_url = reverse_lazy("accounts:password_change")

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field in form.fields.values():
            field.widget.attrs["class"] = "a-input"
        return form

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({
            "title": "Ganti Password",
            "subtitle": "Gunakan password yang kuat dan belum pernah dipakai di tempat lain.",
            "submit_label": "Ganti Password",
            **_settings_context("password"),
        })
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Password berhasil diganti.")
        return super().form_valid(form)


@login_required
def delete_account(request):
    form = DeleteAccountForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = request.user
        profile = get_profile(user)
        if profile.avatar:
            profile.avatar.delete(save=False)
        logout(request)
        user.delete()
        messages.info(request, "Akunmu sudah dihapus.")
        return redirect("core:home")
    return render(request, "accounts/form_page.html", {
        "form": form,
        "title": "Hapus Akun",
        "subtitle": "Tindakan ini permanen: profil dan data akunmu akan dihapus. "
                    "Masukkan password untuk konfirmasi.",
        "submit_label": "Hapus Akun Saya",
        "danger": True,
        "cancel_url": reverse("accounts:me"),
        **_settings_context("delete"),
    })
