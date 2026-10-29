from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.wardrobe.cleanup import cleanup_pending_photos
from apps.wardrobe.models import WardrobeItemImage, WardrobePhotoCleanup
from .test_private_photos import png_upload


class CleanupCommandTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        settings = override_settings(WARDROBE_PRIVATE_ROOT=self.root)
        settings.enable()
        self.addCleanup(settings.disable)
        self.storage = WardrobeItemImage._meta.get_field("image").storage

    def pending(self, filename):
        name = self.storage.save(f"photos/{filename}", png_upload(filename))
        return WardrobePhotoCleanup.objects.create(file_name=name)

    def run_command(self, **kwargs):
        output = StringIO()
        call_command("cleanup_wardrobe_photos", stdout=output, **kwargs)
        return output.getvalue()

    def test_empty_queue(self):
        self.assertIn("Tidak ada antrean", self.run_command())

    def test_success_in_small_batches_and_unqueued_file_is_untouched(self):
        jobs = [self.pending(f"retry-{i}.png") for i in range(3)]
        unqueued = self.storage.save("photos/not-queued.png", png_upload())
        output = self.run_command(batch_size=1)
        self.assertIn("Diproses: 3; selesai: 3; masih tertunda: 0", output)
        self.assertFalse(WardrobePhotoCleanup.objects.exists())
        self.assertTrue(all(not self.storage.exists(job.file_name) for job in jobs))
        self.assertTrue(self.storage.exists(unqueued))

    def test_failed_job_does_not_block_next_batch_and_can_be_retried(self):
        failed = self.pending("failed.png")
        success = self.pending("success.png")
        original_delete = self.storage.delete

        def fail_one(name):
            if name == failed.file_name:
                raise OSError("temporary storage failure")
            return original_delete(name)

        with self.assertLogs("apps.wardrobe.cleanup", level="ERROR"):
            with patch.object(self.storage, "delete", side_effect=fail_one) as delete:
                with self.assertRaises(CommandError):
                    self.run_command(batch_size=1)
        self.assertEqual(delete.call_count, 2)
        self.assertTrue(WardrobePhotoCleanup.objects.filter(pk=failed.pk).exists())
        self.assertTrue(self.storage.exists(failed.file_name))
        self.assertFalse(WardrobePhotoCleanup.objects.filter(pk=success.pk).exists())
        self.assertFalse(self.storage.exists(success.file_name))
        self.assertIn("selesai: 1; masih tertunda: 0", self.run_command())
        self.assertFalse(WardrobePhotoCleanup.objects.exists())

    def test_missing_file_is_safe_and_repeated_command_is_safe(self):
        WardrobePhotoCleanup.objects.create(file_name="photos/already-removed.png")
        self.assertIn("selesai: 1", self.run_command())
        self.assertIn("Tidak ada antrean", self.run_command())

    def test_invalid_batch_size(self):
        for size in (0, -1):
            with self.subTest(size=size):
                with self.assertRaisesMessage(CommandError, "lebih besar dari nol"):
                    self.run_command(batch_size=size)

    def test_new_jobs_wait_until_next_run(self):
        original = self.pending("original.png")
        added = []

        def add_job_then_cleanup(ids):
            added.append(self.pending("new.png"))
            cleanup_pending_photos(ids)

        with patch("apps.wardrobe.management.commands.cleanup_wardrobe_photos.cleanup_pending_photos", side_effect=add_job_then_cleanup):
            self.assertIn("Diproses: 1", self.run_command(batch_size=1))
        self.assertFalse(self.storage.exists(original.file_name))
        self.assertEqual(WardrobePhotoCleanup.objects.count(), 1)
        self.assertTrue(self.storage.exists(added[0].file_name))
        self.run_command()
        self.assertFalse(WardrobePhotoCleanup.objects.exists())
