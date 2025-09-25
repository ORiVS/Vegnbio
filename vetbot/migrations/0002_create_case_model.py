from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone

class Migration(migrations.Migration):

    dependencies = [
        ("vetbot", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Case",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("user_text", models.TextField(blank=True)),
                ("extracted_symptoms", models.JSONField(default=list, blank=True)),
                ("symptom_codes", models.JSONField(default=list, blank=True)),
                ("triage", models.CharField(max_length=10, choices=[("low", "Low"), ("medium", "Medium"), ("high", "High")], blank=True)),
                ("differential", models.JSONField(default=list, blank=True)),
                ("advice", models.TextField(blank=True)),
                ("model_trace", models.JSONField(default=dict, blank=True)),
                ("created_at", models.DateTimeField(default=timezone.now)),
                ("species", models.ForeignKey(to="vetbot.species", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="cases")),
                ("breed", models.ForeignKey(to="vetbot.breed", null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, related_name="cases")),
            ],
        ),
    ]
