import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contracts", "0009_basecontract"),
        ("catalog", "0024_item_stage"),
    ]

    operations = [
        migrations.RenameField(
            model_name="item",
            old_name="old_name",
            new_name="new_name",
        ),
        migrations.AddField(
            model_name="item",
            name="base_contract",
            field=models.ForeignKey(
                default=None,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="items",
                to="contracts.basecontract",
            ),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="stage",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("review", "In review"),
                    ("approved", "Approved"),
                    ("closed", "Closed"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
    ]
