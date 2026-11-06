from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0017_order_status_index"),
    ]

    operations = [
        migrations.CreateModel(
            name="NewConfig",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("key", models.CharField(max_length=100, unique=True)),
                ("value", models.TextField(blank=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.DeleteModel(
            name="OldConfig",
        ),
        migrations.RemoveField(
            model_name="order",
            name="legacy_ref",
        ),
        migrations.RemoveField(
            model_name="order",
            name="internal_note",
        ),
    ]
