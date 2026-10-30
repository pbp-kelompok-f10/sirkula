# Adopt the existing category table without changing its rows or sequence.

import django.db.models.deletion
import django.db.models.functions.text
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('main', '0002_move_category_state'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name='Category',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('name', models.CharField(max_length=100)),
                        ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='wardrobe_categories', to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        'db_table': 'main_category',
                        'ordering': ['name', 'id'],
                        'constraints': [models.UniqueConstraint(django.db.models.functions.text.Lower('name'), models.F('owner'), name='unique_wardrobe_category_name_per_owner')],
                    },
                ),
            ],
        ),
    ]
