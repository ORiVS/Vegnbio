from django.core.management.base import BaseCommand
from django.db import transaction
from vetbot.models import Feedback, Disease, DiseaseSymptom, Symptom

# règles simples:
# - pour chaque feedback by_vet=True avec validated_diagnosis non vide:
#   * +0.03 sur prevalence de la maladie (max 0.8)
#   * pour chaque symptôme du case, +0.05 sur le poids du lien (max 2.5) si le lien existe

class Command(BaseCommand):
    help = "Ajuste légèrement les poids et prévalences à partir des feedbacks validés par vétérinaire."

    def handle(self, *args, **kwargs):
        adjusted = 0
        with transaction.atomic():
            fbs = Feedback.objects.select_related("case").filter(by_vet=True).exclude(validated_diagnosis="")
            for fb in fbs:
                diag_name = fb.validated_diagnosis.strip()
                if not fb.case or not diag_name:
                    continue
                disease = Disease.objects.filter(name__iexact=diag_name, species=fb.case.species).first()
                if not disease:
                    continue

                # prevalence
                old_prev = float(disease.prevalence or 0.0)
                new_prev = min(old_prev + 0.03, 0.8)
                if new_prev != old_prev:
                    disease.prevalence = new_prev
                    disease.save(update_fields=["prevalence"])
                    adjusted += 1

                # poids symptômes observés
                if isinstance(fb.case.symptom_codes, list):
                    for code in fb.case.symptom_codes:
                        try:
                            link = DiseaseSymptom.objects.select_related("symptom").get(
                                disease=disease, symptom__code=code
                            )
                            old_w = float(link.weight or 0.0)
                            new_w = min(old_w + 0.05, 2.5)
                            if new_w != old_w:
                                link.weight = new_w
                                link.save(update_fields=["weight"])
                                adjusted += 1
                        except DiseaseSymptom.DoesNotExist:
                            # pas de lien -> on ignore (on peut aussi le créer si tu veux, mais on reste prudent)
                            pass

        self.stdout.write(self.style.SUCCESS(f"Apprentissage terminé. Paramètres ajustés: {adjusted}"))
