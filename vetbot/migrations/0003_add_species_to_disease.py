from django.db import migrations, models
import django.db.models.deletion

def ensure_default_species_and_backfill(apps, schema_editor):
    Species = apps.get_model("vetbot", "Species")
    Disease = apps.get_model("vetbot", "Disease")
    # Garantir une espèce par défaut
    default = Species.objects.order_by("id").first()
    if default is None:
        default = Species.objects.create(code="general", name="Généraliste")
    # Backfill
    Disease.objects.filter(species__isnull=True).update(species=default)

class Migration(migrations.Migration):

    dependencies = [
        ("vetbot", "0002_create_case_model"),
    ]

    operations = [
        # 1) Côté base de données : créer la colonne si absente
        migrations.RunSQL(
            sql=[
                # colonne nullable au début
                ("ALTER TABLE \"vetbot_disease\" ADD COLUMN IF NOT EXISTS \"species_id\" bigint;", []),
                # (optionnel) créer l'index simple si tu veux déjà accélérer le backfill
                # ("CREATE INDEX IF NOT EXISTS vetbot_disease_species_id_idx ON \"vetbot_disease\" (\"species_id\");", []),
            ],
            reverse_sql=[
                # ne pas supprimer la colonne au rollback (pour rester safe)
            ],
        ),

        # 2) Côté "state" Django : dire au framework que le champ existe,
        #    sans tenter de le recréer (on évite l'erreur "already exists")
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="disease",
                    name="species",
                    field=models.ForeignKey(
                        to="vetbot.species",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="diseases",
                        null=True,
                        blank=True,
                    ),
                ),
            ],
            database_operations=[
                # rien ici : la DB a déjà la colonne via RunSQL ci-dessus
            ],
        ),

        # 3) Backfill des valeurs nulles
        migrations.RunPython(ensure_default_species_and_backfill, migrations.RunPython.noop),
    ]
