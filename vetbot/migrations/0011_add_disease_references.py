from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ("vetbot", "0010_rename_vetbot_dise_species_code_idx_vetbot_dise_species_6d3a63_idx_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                # --- Disease ---
                'ALTER TABLE "vetbot_disease"  ADD COLUMN IF NOT EXISTS "species_id" bigint;',
                'ALTER TABLE "vetbot_disease"  ADD COLUMN IF NOT EXISTS "code" varchar(64);',
                'ALTER TABLE "vetbot_disease"  ADD COLUMN IF NOT EXISTS "description" text;',
                'ALTER TABLE "vetbot_disease"  ADD COLUMN IF NOT EXISTS "prevalence" double precision;',
                'ALTER TABLE "vetbot_disease"  ADD COLUMN IF NOT EXISTS "references" jsonb;',
                # Valeurs par défaut pour les nouvelles colonnes si créées à l’instant
                'UPDATE "vetbot_disease" SET "prevalence" = 0.0 WHERE "prevalence" IS NULL;',
                'UPDATE "vetbot_disease" SET "references" = \'[]\'::jsonb WHERE "references" IS NULL;',

                # --- Feedback ---
                'ALTER TABLE "vetbot_feedback" ADD COLUMN IF NOT EXISTS "case_id" bigint;',

                # --- Breed ---
                'ALTER TABLE "vetbot_breed"    ADD COLUMN IF NOT EXISTS "aliases" jsonb;',
                'UPDATE "vetbot_breed" SET "aliases" = \'[]\'::jsonb WHERE "aliases" IS NULL;',

                # --- Symptom ---
                'ALTER TABLE "vetbot_symptom"  ADD COLUMN IF NOT EXISTS "snomed_id" varchar(32);',
                'ALTER TABLE "vetbot_symptom"  ADD COLUMN IF NOT EXISTS "venom_code" varchar(32);',
            ],
            reverse_sql=[],
        ),
    ]
