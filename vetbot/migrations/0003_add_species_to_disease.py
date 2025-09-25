from django.db import migrations, models
import django.db.models.deletion

def ensure_default_species_and_backfill(apps, schema_editor):
    Species = apps.get_model("vetbot", "Species")
    Disease = apps.get_model("vetbot", "Disease")
    # Crée une espèce par défaut si aucune n'existe
    default = Species.objects.order_by("id").first()
    if default is None:
        default = Species.objects.create(code="general", name="Généraliste")
    # Backfill des maladies existantes
    Disease.objects.filter(species__isnull=True).update(species=default)

class Migration(migrations.Migration):

    dependencies = [
        ("vetbot", "0002_create_case_model"),
    ]

    operations = [
        migrations.AddField(
            model_name="disease",
            name="species",
            field=models.ForeignKey(
                to="vetbot.species",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="diseases",
                null=True,  # nullable d'abord
                blank=True,
            ),
        ),
        migrations.RunPython(ensure_default_species_and_backfill, migrations.RunPython.noop),
    ]
