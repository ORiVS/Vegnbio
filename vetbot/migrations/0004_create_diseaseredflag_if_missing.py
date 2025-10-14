from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('vetbot', '0003_add_weight_critical_to_diseasesymptom'),
    ]

    operations = [
        # 1) Crée la table en SQL si elle n'existe pas (idempotent)
        migrations.RunSQL(
            sql="""
                CREATE TABLE IF NOT EXISTS "vetbot_diseaseredflag" (
                    "id" bigserial PRIMARY KEY,
                    "text" varchar(256) NOT NULL,
                    "disease_id" bigint NOT NULL
                );
                -- FK (si elle n'existe pas déjà, Postgres l'ignorera si doublon exact)
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM information_schema.table_constraints
                        WHERE constraint_name = 'vetbot_diseaseredflag_disease_id_fk'
                    ) THEN
                        ALTER TABLE "vetbot_diseaseredflag"
                        ADD CONSTRAINT vetbot_diseaseredflag_disease_id_fk
                        FOREIGN KEY ("disease_id")
                        REFERENCES "vetbot_disease" ("id")
                        ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;
                    END IF;
                END$$;
                -- Index pour les perfs
                CREATE INDEX IF NOT EXISTS "vetbot_diseaseredflag_disease_id_idx"
                ON "vetbot_diseaseredflag" ("disease_id");
            """,
            reverse_sql="""
                DROP TABLE IF EXISTS "vetbot_diseaseredflag";
            """,
        ),

        # 2) Mets l'ETAT Django en phase (sans refaire d'ALTER TABLE)
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name='DiseaseRedFlag',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('text', models.CharField(max_length=256)),
                        ('disease', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='red_flags', to='vetbot.disease')),
                    ],
                    options={},
                ),
            ],
        ),
    ]
