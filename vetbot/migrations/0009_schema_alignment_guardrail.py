from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ("vetbot", "0008_add_symptom_optional_columns"),  # adapte si ton dernier numéro est différent
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                # Tables/colonnes clés — toutes en IF NOT EXISTS
                'ALTER TABLE "vetbot_disease"  ADD COLUMN IF NOT EXISTS "species_id" bigint;',
                'ALTER TABLE "vetbot_disease"  ADD COLUMN IF NOT EXISTS "code" varchar(64);',
                'ALTER TABLE "vetbot_feedback" ADD COLUMN IF NOT EXISTS "case_id" bigint;',
                'ALTER TABLE "vetbot_breed"    ADD COLUMN IF NOT EXISTS "aliases" jsonb;',
                'ALTER TABLE "vetbot_symptom"  ADD COLUMN IF NOT EXISTS "snomed_id" varchar(32);',
                'ALTER TABLE "vetbot_symptom"  ADD COLUMN IF NOT EXISTS "venom_code" varchar(32);',

                # Valeurs par défaut si créées à l’instant
                'UPDATE "vetbot_breed"   SET "aliases" = \'[]\'::jsonb WHERE "aliases" IS NULL;',
                # (tu peux ajouter d’autres backfills “safe” ici si besoin)
            ],
            reverse_sql=[],
        ),
    ]
