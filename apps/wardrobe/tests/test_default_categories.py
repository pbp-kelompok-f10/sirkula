from io import StringIO
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.db.models.signals import post_save
from django.test import TestCase
from django.urls import reverse

from apps.wardrobe.defaults import DEFAULT_CATEGORY_NAMES, ensure_default_categories
from apps.wardrobe.models import Category, WardrobeItem, WardrobeItemImage


class DefaultCategoryTests(TestCase):
    def setUp(self):
        self.User = get_user_model()

    def test_new_user_gets_exactly_five_owned_defaults(self):
        owner = self.User.objects.create_user(username="default-owner")
        self.assertCountEqual(owner.wardrobe_categories.values_list("name", flat=True), DEFAULT_CATEGORY_NAMES)
        self.assertEqual(Category.objects.count(), 5)

    def test_superuser_and_direct_model_creation_also_receive_defaults(self):
        admin = self.User.objects.create_superuser(username="default-admin", password="test-only-password")
        direct = self.User.objects.create(username="default-direct")
        for owner in (admin, direct):
            self.assertCountEqual(owner.wardrobe_categories.values_list("name", flat=True), DEFAULT_CATEGORY_NAMES)

    def test_defaults_are_separate_records_for_each_owner(self):
        first = self.User.objects.create_user(username="default-first")
        second = self.User.objects.create_user(username="default-second")
        self.assertEqual(Category.objects.count(), 10)
        self.assertFalse(set(first.wardrobe_categories.values_list("pk", flat=True)) & set(second.wardrobe_categories.values_list("pk", flat=True)))

    def test_user_update_and_login_do_not_recreate_deleted_or_renamed_defaults(self):
        owner = self.User.objects.create_user(username="default-update", password="test-only-password")
        owner.wardrobe_categories.get(name="Kaos").delete()
        category = owner.wardrobe_categories.get(name="Outer")
        category.name = "Jaket favorit"
        category.save()
        before = list(owner.wardrobe_categories.values_list("pk", "name"))
        owner.first_name = "Baru"
        owner.save()
        self.assertTrue(self.client.login(username=owner.username, password="test-only-password"))
        for _ in range(2):
            self.assertEqual(self.client.get(reverse("wardrobe:index")).status_code, 200)
        self.assertEqual(list(owner.wardrobe_categories.values_list("pk", "name")), before)

    def test_raw_fixture_user_is_not_seeded_and_regular_update_does_not_backfill(self):
        owner = self.User(username="default-fixture")
        owner.save_base(raw=True)
        self.assertFalse(owner.wardrobe_categories.exists())
        owner.save()
        self.assertFalse(owner.wardrobe_categories.exists())

    def test_signal_registration_is_not_duplicated(self):
        apps.get_app_config("wardrobe").ready()
        apps.get_app_config("wardrobe").ready()
        with patch("apps.wardrobe.signals.ensure_default_categories", wraps=ensure_default_categories) as seed:
            owner = self.User.objects.create_user(username="default-registration")
        seed.assert_called_once_with(owner.pk, using="default")
        self.assertEqual(owner.wardrobe_categories.count(), 5)

    def test_case_insensitive_backfill_preserves_existing_ids_and_names(self):
        owner = self.User.objects.create_user(username="default-case")
        owner.wardrobe_categories.all().delete()
        existing = [Category.objects.create(owner=owner, name=name) for name in ("kaos", "CELANA", "kEmEjA", "OUTER", "sepatu", "Favorit")]
        before = list(owner.wardrobe_categories.values_list("pk", "name"))
        self.assertEqual(ensure_default_categories(owner.pk), 0)
        self.assertEqual(ensure_default_categories(owner.pk), 0)
        self.assertEqual(list(owner.wardrobe_categories.values_list("pk", "name")), before)
        for category in existing[:5]:
            self.assertEqual(owner.wardrobe_categories.filter(name__iexact=category.name).count(), 1)

    def test_database_still_rejects_duplicate_capital_for_same_owner(self):
        owner = self.User.objects.create_user(username="default-unique")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Category.objects.create(owner=owner, name="KAOS")
        self.assertEqual(owner.wardrobe_categories.count(), 5)

    def test_helper_rolls_back_partial_categories_when_database_fails(self):
        owner = self.User.objects.create_user(username="default-rollback")
        owner.wardrobe_categories.all().delete()
        manager_method = Category.objects.all().__class__.get_or_create
        calls = 0
        def fail_second(queryset, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise IntegrityError("simulated category write failure")
            return manager_method(queryset, *args, **kwargs)
        with patch("django.db.models.query.QuerySet.get_or_create", new=fail_second):
            with self.assertRaises(IntegrityError):
                ensure_default_categories(owner.pk)
        self.assertFalse(owner.wardrobe_categories.exists())
        self.assertEqual(ensure_default_categories(owner.pk), 5)


class SeedCategoryCommandTests(TestCase):
    def command(self, **kwargs):
        output = StringIO()
        call_command("seed_wardrobe_categories", stdout=output, **kwargs)
        return output.getvalue()

    def test_no_users_is_a_successful_noop(self):
        output = self.command()
        self.assertIn("Pengguna diproses: 0", output)
        self.assertIn("kategori ditambahkan: 0", output)

    def test_command_completes_old_users_and_is_idempotent(self):
        User = get_user_model()
        owner = User.objects.create_user(username="seed-existing")
        other = User.objects.create_user(username="seed-empty")
        owner.wardrobe_categories.all().delete()
        other.wardrobe_categories.all().delete()
        existing = Category.objects.create(owner=owner, name="kaos")
        custom = Category.objects.create(owner=owner, name="Pakaian favorit")
        item = WardrobeItem.objects.create(owner=owner, category=existing, name="Koleksi lama")
        photo = WardrobeItemImage.objects.create(item=item, image="photos/reference-only.png", position=1)
        before_item = list(WardrobeItem.objects.values_list("pk", "category_id", "name", "status", "updated_at"))
        before_photo = list(WardrobeItemImage.objects.values_list("pk", "item_id", "image", "position"))
        output = self.command(database="default")
        self.assertIn("Pengguna diproses: 2", output)
        self.assertIn("kategori ditambahkan: 9", output)
        self.assertEqual(owner.wardrobe_categories.count(), 6)
        self.assertEqual(other.wardrobe_categories.count(), 5)
        existing.refresh_from_db()
        self.assertEqual(existing.name, "kaos")
        self.assertTrue(Category.objects.filter(pk=custom.pk, name=custom.name).exists())
        self.assertEqual(list(WardrobeItem.objects.values_list("pk", "category_id", "name", "status", "updated_at")), before_item)
        self.assertEqual(list(WardrobeItemImage.objects.values_list("pk", "item_id", "image", "position")), before_photo)
        snapshot = list(Category.objects.order_by("pk").values_list("pk", "owner_id", "name"))
        self.assertIn("kategori ditambahkan: 0", self.command())
        self.assertEqual(list(Category.objects.order_by("pk").values_list("pk", "owner_id", "name")), snapshot)
        photo.refresh_from_db()
        self.assertEqual(photo.image.name, "photos/reference-only.png")

    def test_command_is_the_explicit_way_to_restore_missing_defaults(self):
        owner = get_user_model().objects.create_user(username="seed-deleted")
        owner.wardrobe_categories.get(name="Sepatu").delete()
        self.client.force_login(owner)
        self.client.get(reverse("wardrobe:index"))
        self.assertFalse(owner.wardrobe_categories.filter(name="Sepatu").exists())
        self.assertIn("kategori ditambahkan: 1", self.command())
        self.assertCountEqual(owner.wardrobe_categories.values_list("name", flat=True), DEFAULT_CATEGORY_NAMES)
