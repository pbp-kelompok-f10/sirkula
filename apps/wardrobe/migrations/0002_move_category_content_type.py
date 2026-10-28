from django.db import migrations


def move_content_type(apps, schema_editor, source, target):
    ContentType = apps.get_model("contenttypes", "ContentType")
    objects = ContentType.objects.using(schema_editor.connection.alias)
    old = objects.filter(app_label=source, model="category").first()
    if old is None:
        return
    if objects.filter(app_label=target, model="category").exists():
        raise RuntimeError("Category content types conflict; review permissions before continuing.")
    # Keep the ID so permission, group, and user links remain intact.
    objects.filter(pk=old.pk).update(app_label=target)


def forwards(apps, schema_editor):
    move_content_type(apps, schema_editor, "main", "wardrobe")


def backwards(apps, schema_editor):
    move_content_type(apps, schema_editor, "wardrobe", "main")


class Migration(migrations.Migration):
    dependencies = [
        ("wardrobe", "0001_adopt_category"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]
    operations = [migrations.RunPython(forwards, backwards)]
