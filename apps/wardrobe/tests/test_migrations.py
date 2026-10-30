from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class CategoryMoveMigrationTests(TransactionTestCase):
    def setUp(self):
        executor = MigrationExecutor(connection)
        self.latest = executor.loader.graph.leaf_nodes()
        self.other_targets = [node for node in self.latest if node[0] not in {"main", "wardrobe", "outfits"}]
        self.old_target = self.other_targets + [("main", "0001_initial"), ("outfits", "0001_initial")]
        executor.migrate(self.old_target + [("wardrobe", None)])
        self.old_apps = executor.loader.project_state(self.old_target).apps
        HistoricalUser = self.old_apps.get_model("auth", "User")
        self.owner = HistoricalUser.objects.create(username="migration-owner")
        self.other = HistoricalUser.objects.create(username="migration-other")
        self.owner = get_user_model().objects.get(pk=self.owner.pk)
        self.other = get_user_model().objects.get(pk=self.other.pk)
        Category = self.old_apps.get_model("main", "Category")
        Category.objects.create(pk=201, name="Kaos", owner_id=self.owner.pk)
        Category.objects.create(pk=305, name="Kaos", owner_id=self.other.pk)
        self.snapshot = list(Category.objects.order_by("pk").values_list("pk", "name", "owner_id"))
        content_type = ContentType.objects.get(app_label="main", model="category")
        self.content_type_id = content_type.pk
        self.permission, _ = Permission.objects.get_or_create(
            content_type=content_type, codename="change_category", defaults={"name": "Can change category"}
        )
        self.group = Group.objects.create(name="Category editors")
        self.group.permissions.add(self.permission)
        self.owner.groups.add(self.group)
        self.owner.user_permissions.add(self.permission)

    def tearDown(self):
        MigrationExecutor(connection).migrate(self.latest)
        ContentType.objects.clear_cache()
        super().tearDown()

    def test_data_ids_permissions_sequence_and_reverse_are_preserved(self):
        MigrationExecutor(connection).migrate(self.latest)
        from apps.wardrobe.models import Category

        self.assertEqual(Category._meta.db_table, "main_category")
        self.assertEqual(list(Category.objects.order_by("pk").values_list("pk", "name", "owner_id")), self.snapshot)
        self.assertFalse(ContentType.objects.filter(app_label="main", model="category").exists())
        self.assertEqual(ContentType.objects.get(app_label="wardrobe", model="category").pk, self.content_type_id)
        self.assertTrue(self.group.permissions.filter(pk=self.permission.pk).exists())
        self.assertTrue(self.owner.user_permissions.filter(pk=self.permission.pk).exists())
        self.assertTrue(get_user_model().objects.get(pk=self.owner.pk).has_perm("wardrobe.change_category"))
        new_category = Category.objects.create(name="Outer", owner_id=self.owner.pk)
        self.assertGreater(new_category.pk, 305)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Category.objects.create(name="kaos", owner_id=self.owner.pk)
        complete_snapshot = list(Category.objects.order_by("pk").values_list("pk", "name", "owner_id"))

        executor = MigrationExecutor(connection)
        executor.migrate(self.old_target + [("wardrobe", None)])
        OldCategory = executor.loader.project_state(self.old_target).apps.get_model("main", "Category")
        self.assertEqual(list(OldCategory.objects.order_by("pk").values_list("pk", "name", "owner_id")), complete_snapshot)
        self.assertEqual(ContentType.objects.get(app_label="main", model="category").pk, self.content_type_id)
        self.assertTrue(self.group.permissions.filter(pk=self.permission.pk).exists())
        self.assertTrue(self.owner.user_permissions.filter(pk=self.permission.pk).exists())
        MigrationExecutor(connection).migrate(self.latest)
        self.assertEqual(list(Category.objects.order_by("pk").values_list("pk", "name", "owner_id")), complete_snapshot)
