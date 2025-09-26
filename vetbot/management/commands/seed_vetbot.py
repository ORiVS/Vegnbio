# vetbot/management/commands/seed_vetbot.py
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.apps import apps
from typing import Dict, Any, Iterable

# ---------- Utilitaires robustes ----------

def table_has_column(table_name: str, column_name: str) -> bool:
    """
    True si la colonne existe physiquement en base (via information_schema).
    table_name doit être en minuscules (ex: "vetbot_disease").
    """
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = %s AND column_name = %s
            LIMIT 1
            """,
            [table_name, column_name],
        )
        return cur.fetchone() is not None


def present_fields(model) -> set[str]:
    """
    Ensemble des champs ORM du modèle (pour filtrer les kwargs).
    """
    return {
        f.name
        for f in model._meta.get_fields()
        if hasattr(f, "attname")
    }


def filter_defaults(model, defaults: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ne garde dans defaults que les clés réellement présentes sur le modèle.
    """
    pf = present_fields(model)
    return {k: v for k, v in defaults.items() if k in pf}


def upsert(model, lookup: Dict[str, Any], defaults: Dict[str, Any]) -> tuple[Any, bool]:
    """
    update_or_create avec filtrage des defaults.
    """
    defaults = filter_defaults(model, defaults)
    if not defaults:
        return model.objects.get_or_create(**lookup)
    return model.objects.update_or_create(**lookup, defaults=defaults)


# ---------- Données d’exemple ----------

SPECIES_DATA: Iterable[Dict[str, Any]] = [
    {"code": "dog", "name": "Chien"},
    {"code": "cat", "name": "Chat"},
]

BREEDS_DATA: Iterable[Dict[str, Any]] = [
    {"species_code": "dog", "name": "Labrador Retriever", "aliases": ["Lab"]},
    {"species_code": "cat", "name": "Européen", "aliases": []},
]

SYMPTOMS_DATA: Iterable[Dict[str, Any]] = [
    {"code": "fever", "label": "Fièvre", "snomed_id": "", "venom_code": ""},
    {"code": "vomiting", "label": "Vomissements", "snomed_id": "", "venom_code": ""},
]

DISEASES_DATA: Iterable[Dict[str, Any]] = [
    {
        "name": "Gastro-entérite",
        "code": "gastro",
        "species_code": "dog",
        "prevalence": 0.1,
        "references": [],
        "description": "Inflammation gastro-intestinale",
        "severity": 0,
    },
    {
        "name": "Coryza",
        "code": "coryza",
        "species_code": "cat",
        "prevalence": 0.2,
        "references": [],
        "description": "Complexe respiratoire félin",
        "severity": 0,
    },
]


# ---------- Commande principale ----------

class Command(BaseCommand):
    help = "Seed VetBot data safely (idempotent et tolérant au schéma)."

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true",
                            help="Échoue si une condition n’est pas satisfaite (sinon on skippe).")
        parser.add_argument("--dry-run", action="store_true",
                            help="Vérifie sans écrire (rollback).")

    @transaction.atomic
    def handle(self, *args, **opts):
        strict: bool = opts["strict"]
        dry: bool = opts["dry_run"]

        self.stdout.write(self.style.NOTICE("Seeding VetBot data..."))

        Species = apps.get_model("vetbot", "Species")
        Breed   = apps.get_model("vetbot", "Breed")
        Symptom = apps.get_model("vetbot", "Symptom")
        Disease = apps.get_model("vetbot", "Disease")

        # --- Détection colonnes en base ---
        breed_has_aliases       = table_has_column("vetbot_breed", "aliases")
        disease_has_code        = table_has_column("vetbot_disease", "code")
        disease_has_species_fk  = table_has_column("vetbot_disease", "species_id")
        disease_has_references  = table_has_column("vetbot_disease", "references")
        disease_has_description = table_has_column("vetbot_disease", "description")
        disease_has_prevalence  = table_has_column("vetbot_disease", "prevalence")
        disease_has_severity    = table_has_column("vetbot_disease", "severity")
        symptom_has_snomed      = table_has_column("vetbot_symptom", "snomed_id")
        symptom_has_venom       = table_has_column("vetbot_symptom", "venom_code")

        disease_model_fields = present_fields(Disease)

        # --- Patch DB si "severity" existe mais pas dans le modèle ---
        if disease_has_severity and ("severity" not in disease_model_fields):
            with connection.cursor() as cur:
                cur.execute("ALTER TABLE vetbot_disease ALTER COLUMN severity SET DEFAULT 0;")
                cur.execute("UPDATE vetbot_disease SET severity = 0 WHERE severity IS NULL;")

        # ---------- 1) Species ----------
        for s in SPECIES_DATA:
            upsert(
                Species,
                lookup={"code": s["code"]},
                defaults={"name": s["name"]},
            )
        self.stdout.write(self.style.SUCCESS(f"Species OK: {[s['code'] for s in SPECIES_DATA]}"))

        # ---------- 2) Breed ----------
        species_by_code = {sp.code: sp for sp in Species.objects.all()}
        for b in BREEDS_DATA:
            sp = species_by_code.get(b["species_code"])
            if not sp:
                if strict:
                    raise RuntimeError(f"Species {b['species_code']} introuvable pour race {b['name']}")
                continue

            defaults = {"name": b["name"]}
            if breed_has_aliases and "aliases" in present_fields(Breed):
                defaults["aliases"] = b.get("aliases", [])

            upsert(Breed, lookup={"species": sp, "name": b["name"]}, defaults=defaults)
        self.stdout.write(self.style.SUCCESS("Breeds OK"))

        # ---------- 3) Symptom ----------
        for sy in SYMPTOMS_DATA:
            defaults = {"label": sy["label"]}
            if symptom_has_snomed and "snomed_id" in present_fields(Symptom):
                defaults["snomed_id"] = sy.get("snomed_id", "")
            if symptom_has_venom and "venom_code" in present_fields(Symptom):
                defaults["venom_code"] = sy.get("venom_code", "")

            upsert(Symptom, lookup={"code": sy["code"]}, defaults=defaults)
        self.stdout.write(self.style.SUCCESS("Symptoms OK"))

        # ---------- 4) Disease ----------
        for d in DISEASES_DATA:
            defaults = {}

            if disease_has_code and "code" in disease_model_fields:
                defaults["code"] = d.get("code")
            if disease_has_description and "description" in disease_model_fields:
                defaults["description"] = d.get("description", "")
            if disease_has_prevalence and "prevalence" in disease_model_fields:
                defaults["prevalence"] = d.get("prevalence", 0.0)
            if disease_has_references and "references" in disease_model_fields:
                defaults["references"] = d.get("references", [])
            if disease_has_severity and "severity" in disease_model_fields:
                defaults["severity"] = d.get("severity", 0)

            if disease_has_species_fk and "species" in disease_model_fields:
                sp = species_by_code.get(d["species_code"])
                if not sp:
                    if strict:
                        raise RuntimeError(f"Species {d['species_code']} introuvable pour disease {d['name']}")
                else:
                    defaults["species"] = sp

            upsert(Disease, lookup={"name": d["name"]}, defaults=defaults)
        self.stdout.write(self.style.SUCCESS("Diseases OK"))

        if dry:
            raise SystemExit(0)

        self.stdout.write(self.style.SUCCESS("Seed VetBot OK (safe)."))
