from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ("vetbot", "0006_finalize_constraints"),
    ]

    operations = [
        # 1) Ajouter la colonne côté DB si absente (PostgreSQL -> jsonb)
        migrations.RunSQL(
            sql=[
                'ALTER TABLE "vetbot_breed" ADD COLUMN IF NOT EXISTS "aliases" jsonb;',
                # Valeur par défaut [] pour les lignes existantes si la colonne vient d'être créée
                'UPDATE "vetbot_breed" SET "aliases" = \'[]\'::jsonb WHERE "aliases" IS NULL;',
            ],
            reverse_sql=[
                # on ne supprime pas la colonne au rollback (safe)
            ],
        ),
        # 2) Aligner l'état Django sans tenter de recréer la colonne
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="breed",
                    name="aliases",
                    field=models.JSONField(default=list, blank=True),
                ),
            ],
            database_operations=[],
        ),
    ]
