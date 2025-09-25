import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.db import transaction
from vetbot.models import (
    Species, Breed, Symptom,
    Disease, DiseaseSymptom, DiseaseRedFlag
)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

def load_json(name):
    with open(DATA_DIR / name, "r", encoding="utf-8") as f:
        return json.load(f)

class Command(BaseCommand):
    help = "Seed initial data for VetBot (species, breeds, symptoms, diseases)"

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Seeding VetBot data..."))

        # Species
        species_map = {}
        for sp in load_json("species.json"):
            obj, _ = Species.objects.get_or_create(code=sp["code"], defaults={"name": sp["name"]})
            species_map[sp["code"]] = obj
        self.stdout.write(self.style.SUCCESS(f"Species OK: {list(species_map.keys())}"))

        # Breeds (dog)
        dog = species_map.get("dog")
        if dog:
            for b in load_json("breeds_dog.json"):
                Breed.objects.get_or_create(
                    species=dog, name=b["name"],
                    defaults={"aliases": b.get("aliases", [])}
                )
        # Breeds (cat)
        cat = species_map.get("cat")
        if cat:
            for b in load_json("breeds_cat.json"):
                Breed.objects.get_or_create(
                    species=cat, name=b["name"],
                    defaults={"aliases": b.get("aliases", [])}
                )
        self.stdout.write(self.style.SUCCESS("Breeds OK"))

        # Symptoms
        symptom_map = {}
        for s in load_json("symptoms.json"):
            sym, _ = Symptom.objects.get_or_create(code=s["code"], defaults={"label": s["label"]})
            symptom_map[s["code"]] = sym
        self.stdout.write(self.style.SUCCESS(f"Symptoms OK: {len(symptom_map)}"))

        # Diseases per species
        def seed_diseases(filename, species_obj):
            data = load_json(filename)
            for d in data:
                dis, _ = Disease.objects.get_or_create(
                    species=species_obj, code=d["code"],
                    defaults={
                        "name": d["name"],
                        "description": d.get("description", ""),
                        "prevalence": d.get("prevalence", 0.0),
                        "references": d.get("references", [])
                    }
                )
                # link symptoms
                for sl in d.get("symptoms", []):
                    code = sl["code"]
                    if code not in symptom_map:
                        # crée le symptôme à la volée si absent
                        sym = Symptom.objects.create(code=code, label=code)
                        symptom_map[code] = sym
                    DiseaseSymptom.objects.get_or_create(
                        disease=dis, symptom=symptom_map[code],
                        defaults={
                            "weight": float(sl.get("weight", 1.0)),
                            "critical": bool(sl.get("critical", False))
                        }
                    )
                # red flags
                for rf in d.get("red_flags", []):
                    DiseaseRedFlag.objects.get_or_create(disease=dis, text=rf)

        if dog:
            seed_diseases("diseases_dog.json", dog)
        if cat:
            seed_diseases("diseases_cat.json", cat)

        self.stdout.write(self.style.SUCCESS("Diseases OK"))
        self.stdout.write(self.style.SUCCESS("Seeding done."))
