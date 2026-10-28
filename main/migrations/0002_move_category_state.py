from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("main", "0001_initial")]
    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[migrations.DeleteModel(name="Category")],
        ),
    ]
