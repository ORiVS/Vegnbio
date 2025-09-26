from django.db import migrations

SQL = r"""
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'vetbot_disease' AND column_name = 'severity'
  ) THEN
    -- Valeur par défaut côté DB pour les prochains INSERT
    BEGIN
      ALTER TABLE "vetbot_disease" ALTER COLUMN "severity" SET DEFAULT 0;
    EXCEPTION WHEN undefined_column THEN
      -- Rien, compatibilité
    END;

    -- Backfill des lignes existantes
    BEGIN
      UPDATE "vetbot_disease" SET "severity" = 0 WHERE "severity" IS NULL;
    EXCEPTION WHEN undefined_column THEN
      -- Rien
    END;
  END IF;
END
$$;
"""

class Migration(migrations.Migration):

    dependencies = [
        ("vetbot", "0011_schema_catch_all"),  # adapte au dernier fichier que tu as poussé
    ]

    operations = [
        migrations.RunSQL(SQL, reverse_sql=""),
    ]
