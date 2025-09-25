from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ("vetbot", "0004_add_case_to_feedback"),
    ]

    operations = [
        # Rendez NOT NULL maintenant que le backfill est fait
        migrations.AlterField(
            model_name="disease",
            name="species",
            field=models.ForeignKey(
                to="vetbot.species",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="diseases",
                null=False,
                blank=False,
            ),
        ),
        # Si tu veux aussi rendre Feedback.case NOT NULL, décommente ce bloc
        # migrations.AlterField(
        #     model_name="feedback",
        #     name="case",
        #     field=models.ForeignKey(
        #         to="vetbot.case",
        #         on_delete=django.db.models.deletion.CASCADE,
        #         related_name="feedbacks",
        #         null=False,
        #         blank=False,
        #     ),
        # ),

        # Index comme souhaité dans ta 0002 d'origine
        migrations.AddIndex(
            model_name="disease",
            index=models.Index(fields=["species", "code"], name="vetbot_dise_species_code_idx"),
        ),
        migrations.AddIndex(
            model_name="disease",
            index=models.Index(fields=["species", "name"], name="vetbot_dise_species_name_idx"),
        ),
    ]
