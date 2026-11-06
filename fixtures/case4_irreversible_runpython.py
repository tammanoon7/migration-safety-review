# Target database: PostgreSQL
# The events table holds about 30 million rows

from django.db import migrations, models
from django.db.models.functions import Lower


def normalize_event_types(apps, schema_editor):
    Event = apps.get_model("analytics", "Event")
    Event.objects.update(event_type=Lower("event_type"))


class Migration(migrations.Migration):

    dependencies = [
        ("analytics", "0031_event_source"),
    ]

    operations = [
        migrations.RunPython(normalize_event_types),
        migrations.AddIndex(
            model_name="event",
            index=models.Index(
                fields=["occurred_at"],
                name="events_occurred_at_idx",
            ),
        ),
    ]
