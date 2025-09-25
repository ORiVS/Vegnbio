from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ("vetbot", "0003_add_species_to_disease"),
    ]

    operations = [
        migrations.AddField(
            model_name="feedback",
            name="case",
            field=models.ForeignKey(
                to="vetbot.case",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="feedbacks",
                null=True,   # nullable d'abord
                blank=True,
            ),
        ),
    ]
