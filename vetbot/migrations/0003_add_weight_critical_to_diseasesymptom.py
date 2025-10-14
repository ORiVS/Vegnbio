from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('vetbot', '0002_errorlog'),
    ]

    operations = [
        # 1) SQL idempotent (ne plante pas si la colonne existe déjà)
        migrations.RunSQL(
            sql="""
                ALTER TABLE vetbot_diseasesymptom
                ADD COLUMN IF NOT EXISTS weight double precision DEFAULT 1.0;
                ALTER TABLE vetbot_diseasesymptom
                ADD COLUMN IF NOT EXISTS critical boolean DEFAULT false;
            """,
            reverse_sql="""
                ALTER TABLE vetbot_diseasesymptom
                DROP COLUMN IF EXISTS weight;
                ALTER TABLE vetbot_diseasesymptom
                DROP COLUMN IF EXISTS critical;
            """,
        ),

        # 2) Met à jour l'ETAT Django sans ré-exécuter d'ALTER TABLE
        migrations.SeparateDatabaseAndState(
            database_operations=[],   # rien en base (on l'a fait juste au-dessus en SQL idempotent)
            state_operations=[
                migrations.AddField(
                    model_name='diseasesymptom',
                    name='weight',
                    field=models.FloatField(default=1.0),
                ),
                migrations.AddField(
                    model_name='diseasesymptom',
                    name='critical',
                    field=models.BooleanField(default=False),
                ),
            ],
        ),
    ]
