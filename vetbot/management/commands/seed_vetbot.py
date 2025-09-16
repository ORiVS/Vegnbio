from django.core.management.base import BaseCommand
from vetbot.models import Species, Breed, Symptom, Disease, DiseaseSymptom, DiseaseBreedRisk

class Command(BaseCommand):
    help = "Seed minimal data for vetbot"

    def handle(self, *args, **kwargs):
        dog, _ = Species.objects.get_or_create(code="dog", defaults={"name":"Chien"})
        cat, _ = Species.objects.get_or_create(code="cat", defaults={"name":"Chat"})

        labr, _ = Breed.objects.get_or_create(species=dog, name="Labrador Retriever")
        gsd, _ = Breed.objects.get_or_create(species=dog, name="German Shepherd")
        siam, _ = Breed.objects.get_or_create(species=cat, name="Siamois")

        def S(code, label):
            return Symptom.objects.get_or_create(code=code, defaults={"label":label})[0]

        vomiting = S("vomiting", "Vomissements")
        diarrhea = S("diarrhea", "Diarrhée")
        lethargy = S("lethargy", "Léthargie")
        lossapp = S("loss_of_appetite", "Perte d'appétit")
        seizure = S("seizure", "Convulsions")
        bleeding = S("bleeding", "Hémorragie")
        fever = S("fever", "Fièvre")
        dehydration = S("dehydration", "Déshydratation")
        poisoning = S("poisoning", "Intoxication")

        def D(name, severity="medium", species_list=(dog,)):
            d, _ = Disease.objects.get_or_create(name=name, defaults={"severity":severity})
            for sp in species_list:
                d.species.add(sp)
            return d

        gastro = D("Gastro-entérite", "medium", (dog, cat))
        parvo  = D("Parvovirose", "high", (dog,))
        foodp  = D("Intoxication alimentaire", "medium", (dog, cat))

        # Règles must/nice
        def rule(d, must=[], nice=[]):
            for s in must:
                DiseaseSymptom.objects.get_or_create(disease=d, symptom=s, kind="MUST")
            for s in nice:
                DiseaseSymptom.objects.get_or_create(disease=d, symptom=s, kind="NICE")

        rule(gastro, must=[vomiting, diarrhea], nice=[lossapp, lethargy, fever, dehydration])
        rule(parvo,  must=[vomiting, diarrhea], nice=[lethargy, dehydration, fever])
        rule(foodp,  must=[vomiting],           nice=[diarrhea, lossapp, lethargy])

        # Poids de race (exemples)
        DiseaseBreedRisk.objects.get_or_create(disease=parvo, breed=labr, defaults={"weight": 0.10})
        DiseaseBreedRisk.objects.get_or_create(disease=gastro, breed=siam, defaults={"weight": 0.05})

        self.stdout.write(self.style.SUCCESS("vetbot seed done."))
