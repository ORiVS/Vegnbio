from django.db import migrations, models
import django.db.models.deletion

def create_default_species(apps, schema_editor):
    Species = apps.get_model('vetbot', 'Species')
    if not Species.objects.exists():
        Species.objects.create(name='Généraliste')

def backfill_disease_species(apps, schema_editor):
    Species = apps.get_model('vetbot', 'Species')
    Disease = apps.get_model('vetbot', 'Disease')
    default_species = Species.objects.first()
    # Si la table existe déjà sans le champ, AddField va la créer NULL,
    # on rétro-remplit pour permettre de passer Not Null ensuite.
    Disease.objects.filter(species__isnull=True).update(species=default_species)

class Migration(migrations.Migration):

    dependencies = [
        ('vetbot', '0001_initial'),
    ]

    operations = [
        # s'assurer qu'au moins une espèce existe pour le backfill
        migrations.RunPython(create_default_species, migrations.RunPython.noop),

        # ajouter la colonne species_id (nullable pour passer sur données existantes)
        migrations.AddField(
            model_name='disease',
            name='species',
            field=models.ForeignKey(
                to='vetbot.species',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='diseases',
                null=True,
                blank=True,
            ),
        ),

        # rétro-remplir les anciennes lignes
        migrations.RunPython(backfill_disease_species, migrations.RunPython.noop),
    ]
