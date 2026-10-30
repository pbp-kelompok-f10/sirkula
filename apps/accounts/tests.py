import io
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Profile

User = get_user_model()
PW = "Sup3rSecret!x"
TMP_MEDIA = tempfile.mkdtemp()


def png(name="a.png", size=(10, 10)):
    buf = io.BytesIO()
    Image.new("RGB", size, "red").save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), "image/png")


@override_settings(MEDIA_ROOT=TMP_MEDIA)
class AccountsTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.user = User.objects.create_user("mutcuy", "mutcuy@example.com", PW)

    # ---- register ----
    def test_register_creates_user_profile_and_logs_in(self):
        step_one = self.client.post(reverse("accounts:register"), {
            "register_stage": "1",
            "username": "Baru Pratama",
            "email": "Baru@Example.com",
            "password1": PW,
            "password2": PW,
        })
        self.assertRedirects(step_one, reverse("accounts:register_location"))
        pending = self.client.session["pending_registration"]
        self.assertNotIn("password", pending)
        self.assertTrue(check_password(PW, pending["password_hash"]))

        r = self.client.post(reverse("accounts:register_location"), {"address": "Jl. Merdeka No. 7"})
        self.assertRedirects(r, reverse("accounts:login"))

        u = User.objects.get(email="baru@example.com")
        self.assertTrue(Profile.objects.filter(user=u).exists())
        self.assertEqual(u.profile.full_name, "Baru Pratama")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_register_does_not_create_account_before_location_step(self):
        response = self.client.post(reverse("accounts:register"), {
            "username": "Nama Baru", "email": "baru@example.com",
            "password1": PW, "password2": PW,
        })
        self.assertRedirects(response, reverse("accounts:register_location"))
        self.assertFalse(User.objects.filter(email="baru@example.com").exists())

    def test_register_rejects_duplicate_email_case_insensitive(self):
        r = self.client.post(reverse("accounts:register"), {
            "username": "lain", "email": "MUTCUY@example.com",
            "password1": PW, "password2": PW})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="lain").exists())

    def test_register_rejects_password_mismatch(self):
        r = self.client.post(reverse("accounts:register"), {
            "username": "lain", "email": "l@e.com", "password1": PW, "password2": "x"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="lain").exists())

    def test_register_rejects_weak_password(self):
        r = self.client.post(reverse("accounts:register"), {
            "username": "lain", "email": "l@e.com",
            "password1": "password", "password2": "password"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(email="l@e.com").exists())

    # ---- login / logout ----
    def test_login_success_and_next(self):
        url = reverse("accounts:login") + "?next=/accounts/edit/"
        r = self.client.post(url, {"username": "mutcuy@example.com", "password": PW, "next": "/accounts/edit/"})
        self.assertRedirects(r, "/accounts/edit/")

    def test_login_blocks_external_next(self):
        r = self.client.post(reverse("accounts:login"),
                             {"username": "mutcuy@example.com", "password": PW, "next": "https://evil.com/"})
        self.assertRedirects(r, reverse("accounts:me"), fetch_redirect_response=False)

    def test_login_wrong_password(self):
        r = self.client.post(reverse("accounts:login"), {"username": "mutcuy@example.com", "password": "salah"})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_rejects_inactive_account(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        response = self.client.post(reverse("accounts:login"), {
            "username": "mutcuy@example.com", "password": PW,
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_without_remember_me_expires_on_browser_close(self):
        self.client.post(reverse("accounts:login"), {"username": "mutcuy@example.com", "password": PW})
        self.assertTrue(self.client.session.get_expire_at_browser_close())
        self.client.logout()
        self.client.post(reverse("accounts:login"),
                         {"username": "mutcuy@example.com", "password": PW, "remember_me": "on"})
        self.assertFalse(self.client.session.get_expire_at_browser_close())

    def test_logout_requires_post(self):
        self.client.login(username="mutcuy", password=PW)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)
        r = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(r, reverse("core:home"))
        self.assertNotIn("_auth_user_id", self.client.session)

    # ---- akses ----
    def test_settings_pages_require_login(self):
        for name in ["me", "profile_edit", "account_edit", "password_change", "delete_account"]:
            r = self.client.get(reverse(f"accounts:{name}"))
            self.assertEqual(r.status_code, 302, name)
            self.assertIn("/accounts/login/", r["Location"], name)

    def test_profile_public_view_hides_owner_controls(self):
        h = self.client.get(reverse("accounts:profile", args=["mutcuy"])).content.decode()
        self.assertIn("Reputasi Transaksi", h)
        self.assertNotIn("Edit Profil", h)
        self.assertNotIn("Dashboard Saya", h)

    def test_profile_owner_view_and_unknown_user(self):
        self.client.login(username="mutcuy", password=PW)
        h = self.client.get(reverse("accounts:profile", args=["mutcuy"])).content.decode()
        self.assertIn("Edit Profil", h)
        self.assertEqual(self.client.get("/accounts/u/tidakada/").status_code, 404)

    def test_profile_created_for_user_without_profile(self):
        Profile.objects.filter(user=self.user).delete()
        r = self.client.get(reverse("accounts:profile", args=["mutcuy"]))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(Profile.objects.filter(user=self.user).exists())

    def test_profile_page_uses_uploaded_avatar_url(self):
        self.client.login(username="mutcuy", password=PW)
        self.client.post(reverse("accounts:profile_edit"), {"avatar": png("profile.png")})
        profile = Profile.objects.get(user=self.user)
        response = self.client.get(reverse("accounts:profile", args=["mutcuy"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, profile.avatar.url)
        self.assertTrue(profile.avatar.url.startswith("/media/avatars/"))
        self.assertTrue(profile.avatar.storage.exists(profile.avatar.name))

    def test_avatar_fallback_does_not_reference_missing_static_image(self):
        self.client.login(username="mutcuy", password=PW)
        response = self.client.get(reverse("accounts:profile_edit"))
        self.assertContains(response, 'data-avatar-fallback')
        self.assertNotContains(response, "/static/img/avatar.png")

    # ---- edit profil ----
    def test_profile_edit_updates_and_replaces_avatar(self):
        self.client.login(username="mutcuy", password=PW)
        data = {"display_name": "Mutcuy", "full_name": "Mutcuy Lengkap", "bio": "hai",
                "location": "Depok, Jawa Barat"}
        self.client.post(reverse("accounts:profile_edit"), {**data, "avatar": png("one.png")})
        p = Profile.objects.get(user=self.user)
        self.assertEqual((p.display_name, p.location), ("Mutcuy", "Depok, Jawa Barat"))
        first = p.avatar.path
        import os; self.assertTrue(os.path.exists(first))
        self.client.post(reverse("accounts:profile_edit"), {**data, "avatar": png("two.png")})
        p.refresh_from_db()
        self.assertFalse(os.path.exists(first), "file lama harus terhapus")
        self.assertTrue(os.path.exists(p.avatar.path))

    def test_profile_edit_clear_avatar(self):
        self.client.login(username="mutcuy", password=PW)
        self.client.post(reverse("accounts:profile_edit"), {"avatar": png()})
        p = Profile.objects.get(user=self.user); path = p.avatar.path
        self.client.post(reverse("accounts:profile_edit"), {"avatar-clear": "on"})
        p.refresh_from_db()
        import os
        self.assertFalse(p.avatar)
        self.assertFalse(os.path.exists(path))

    def test_avatar_too_large_or_not_image_rejected(self):
        self.client.login(username="mutcuy", password=PW)
        big = SimpleUploadedFile("big.png", b"0" * (2 * 1024 * 1024 + 1), "image/png")
        r = self.client.post(reverse("accounts:profile_edit"), {"avatar": big})
        self.assertEqual(r.status_code, 200)
        txt = SimpleUploadedFile("x.png", b"bukan gambar", "image/png")
        r = self.client.post(reverse("accounts:profile_edit"), {"avatar": txt})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Profile.objects.get(user=self.user).avatar)

    # ---- edit akun ----
    def test_account_edit_changes_username_email(self):
        self.client.login(username="mutcuy", password=PW)
        r = self.client.post(reverse("accounts:account_edit"),
                             {"username": "mutcuy2", "email": "baru@example.com"})
        self.assertEqual(r.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual((self.user.username, self.user.email), ("mutcuy2", "baru@example.com"))

    def test_account_edit_rejects_email_used_by_others_but_allows_own(self):
        User.objects.create_user("orang", "orang@example.com", PW)
        self.client.login(username="mutcuy", password=PW)
        r = self.client.post(reverse("accounts:account_edit"),
                             {"username": "mutcuy", "email": "ORANG@example.com"})
        self.assertEqual(r.status_code, 200)
        r = self.client.post(reverse("accounts:account_edit"),
                             {"username": "mutcuy", "email": "mutcuy@example.com"})
        self.assertEqual(r.status_code, 302)

    # ---- password ----
    def test_password_change_keeps_session_and_new_password_works(self):
        self.client.login(username="mutcuy", password=PW)
        new = "An0therSecret!y"
        r = self.client.post(reverse("accounts:password_change"),
                             {"old_password": PW, "new_password1": new, "new_password2": new})
        self.assertRedirects(r, reverse("accounts:password_change"))
        self.assertEqual(self.client.get(reverse("accounts:me")).status_code, 302)  # masih login
        self.assertIn("/accounts/u/", self.client.get(reverse("accounts:me"))["Location"])
        self.client.logout()
        self.assertTrue(self.client.login(username="mutcuy", password=new))

    def test_password_change_wrong_old_password(self):
        self.client.login(username="mutcuy", password=PW)
        new = "An0therSecret!y"
        r = self.client.post(reverse("accounts:password_change"),
                             {"old_password": "salah", "new_password1": new, "new_password2": new})
        self.assertEqual(r.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PW))

    # ---- hapus akun ----
    def test_delete_account_needs_correct_password(self):
        self.client.login(username="mutcuy", password=PW)
        r = self.client.post(reverse("accounts:delete_account"), {"password": "salah"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_delete_account_removes_user_profile_and_avatar(self):
        self.client.login(username="mutcuy", password=PW)
        self.client.post(reverse("accounts:profile_edit"), {"avatar": png()})
        path = Profile.objects.get(user=self.user).avatar.path
        r = self.client.post(reverse("accounts:delete_account"), {"password": PW})
        self.assertRedirects(r, reverse("core:home"))
        import os
        self.assertFalse(User.objects.filter(username="mutcuy").exists())
        self.assertFalse(Profile.objects.exists())
        self.assertFalse(os.path.exists(path))
        self.assertNotIn("_auth_user_id", self.client.session)
