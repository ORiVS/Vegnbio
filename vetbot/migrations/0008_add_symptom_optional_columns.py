from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ("vetbot", "0007_add_breed_aliases"),  # adapte si ton dernier fichier a un autre numéro
    ]

    operations = [
        # 1) Côté DB : ajouter les colonnes si absentes (PostgreSQL)
        migrations.RunSQL(
            sql=[
                'ALTER TABLE "vetbot_symptom" ADD COLUMN IF NOT EXISTS "snomed_id" varchar(32);',
                'ALTER TABLE "vetbot_symptom" ADD COLUMN IF NOT EXISTS "venom_code" varchar(32);',
            ],
            reverse_sql=[
                # on ne drop pas au rollback (safe)
            ],
        ),
        # 2) Côté état Django : aligner sans re-créer
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="symptom",
                    name="snomed_id",
                    field=models.CharField(max_length=32, blank=True, default=""),
                ),
                migrations.AddField(
                    model_name="symptom",
                    name="venom_code",
                    field=models.CharField(max_length=32, blank=True, default=""),
                ),
            ],
            database_operations=[],
        ),
    ]
