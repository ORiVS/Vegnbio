from django.db import migrations, models
import django.db.models.deletion

def create_default_case(apps, schema_editor):
    Case = apps.get_model('vetbot', 'Case')
    # Crée un "case" minimal si la table est vide (évite les NOT NULL fails ensuite)
    if not Case.objects.exists():
        # Adapte les champs requis de Case si besoin (ex: title/status/etc.)
        try:
            Case.objects.create()  # si tous les champs sont optionnels
        except TypeError:
            # Si des champs sont obligatoires, mets des valeurs par défaut raisonnables :
            fields = {f.name for f in Case._meta.get_fields() if hasattr(f, 'default')}
            payload = {}
            if 'title' in fields:
                payload['title'] = 'Default case'
            Case.objects.create(**payload)

def backfill_feedback_case(apps, schema_editor):
    Case = apps.get_model('vetbot', 'Case')
    Feedback = apps.get_model('vetbot', 'Feedback')
    default_case = Case.objects.first()
    Feedback.objects.filter(case__isnull=True).update(case=default_case)

class Migration(migrations.Migration):

    dependencies = [
        ('vetbot', '0002_add_species_to_disease'),
    ]

    operations = [
        migrations.RunPython(create_default_case, migrations.RunPython.noop),

        migrations.AddField(
            model_name='feedback',
            name='case',
            field=models.ForeignKey(
                to='vetbot.case',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='feedbacks',
                null=True,
                blank=True,
            ),
        ),

        migrations.RunPython(backfill_feedback_case, migrations.RunPython.noop),
    ]
