from django.db import migrations, models

def noop(*args, **kwargs):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ("vetbot", "0004_add_case_to_feedback"),
    ]

    operations = [
        # 1) Créer la colonne côté DB si elle n'existe pas déjà
        migrations.RunSQL(
            sql=[
                # CharField Django -> TEXT en Postgres ; nullable pour passer partout
                ('ALTER TABLE "vetbot_disease" ADD COLUMN IF NOT EXISTS "code" varchar(64);', []),
            ],
            reverse_sql=[
                # Ne pas drop au rollback (safe)
            ],
        ),
        # 2) Mettre l'état Django en phase (sans re-créer la colonne)
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="disease",
                    name="code",
                    field=models.CharField(max_length=64, null=True, blank=True),
                ),
            ],
            database_operations=[],
        ),
    ]
