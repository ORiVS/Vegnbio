# vetbot/views.py
from collections import Counter, defaultdict
from datetime import timedelta
import re

from django.utils import timezone
from django.db.models import Count, Q
from django.conf import settings

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import (
    Symptom, Species, Breed, Disease, DiseaseSymptom, Case, Feedback, ErrorLog
)
from .serializers import (
    ParseInputSerializer, ParseOutputSerializer,
    TriageInputSerializer, TriageOutputSerializer,
    SpeciesSerializer, BreedSerializer, SymptomSerializer, DiseaseDebugSerializer,
    FeedbackInputSerializer, FeedbackOutputSerializer,
    StatsOutputSerializer
)
from .logic.scoring import score_case, decide_triage
from .llm.client import LLMClient
from .llm.prompts import SYSTEM_JSON_EXTRACTOR, SYSTEM_TRIAGE, build_parse_prompt, build_explain_prompt


# --------- Aliases & Fallback helpers ---------

# alias FR->code
SYM_ALIAS = {
    "vomissements": "vomiting",
    "vomissement": "vomiting",
    "fièvre": "fever",
    "fievre": "fever",
    "apathie": "lethargy",
    "fatigue": "lethargy",
    "toux": "cough",
    "éternuements": "sneezing",
    "eternuements": "sneezing",
}

# mots-clés espèces pour le fallback (sans IA)
SPECIES_KEYWORDS = {
    "dog": ["chien", "chiot", "canidé", "canide"],
    "cat": ["chat", "chaton", "félin", "felin"],
}

# mapping simple texte->code symptôme pour le fallback (sans IA)
SYM_TEXT_TO_CODE = {
    # vomiting
    "vomit": "vomiting", "vomissement": "vomiting", "vomissements": "vomiting",
    "régurgite": "vomiting", "regurgite": "vomiting",
    # fever
    "fièvre": "fever", "fievre": "fever", "fièvre.": "fever",
    # lethargy
    "fatigué": "lethargy", "fatigue": "lethargy", "apathie": "lethargy", "mou": "lethargy",
    # cough
    "toux": "cough", "tousser": "cough",
    # sneezing
    "éternue": "sneezing", "éternuements": "sneezing", "eternuements": "sneezing",
}


def _map_symptom_code(code: str) -> str:
    c = (code or "").strip().lower()
    return SYM_ALIAS.get(c, c)


def _log_error(err_type: str, message: str = "", payload: dict | None = None):
    try:
        ErrorLog.objects.create(type=err_type, message=message[:250], payload=payload or {})
    except Exception:
        # on ne casse jamais la réponse pour un problème de log
        pass


def _append_legal_disclaimer(text: str) -> str:
    disclaimer = " Ce service n’est pas un diagnostic. Consultez votre vétérinaire."
    return (text or "").rstrip() + disclaimer


def _fallback_extract(user_text: str) -> dict:
    """
    Plan B sans IA: on devine species, breed="" et quelques symptoms par mots-clés.
    On essaie aussi de capter une durée en jours s'il y a "depuis X jour(s)".
    """
    txt = (user_text or "").lower()

    # species
    species = "unknown"
    for sp, kws in SPECIES_KEYWORDS.items():
        if any(kw in txt for kw in kws):
            species = sp
            break

    # duration_days rudimentaire
    duration_days = None
    m = re.search(r"depuis\s+(\d+)\s*jour", txt)
    if m:
        try:
            duration_days = int(m.group(1))
        except Exception:
            duration_days = None

    # symptoms (uniques)
    found_codes = []
    for needle, code in SYM_TEXT_TO_CODE.items():
        if needle in txt and code not in found_codes:
            found_codes.append(code)

    # construit la liste détaillée
    sym_list = []
    for code in found_codes:
        item = {"code": code}
        if code == "vomiting" and duration_days is not None:
            item["duration_days"] = duration_days
        sym_list.append(item)

    return {"species": species, "breed": "", "symptoms": sym_list}


# --------- Views ---------

class ParseView(APIView):
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        request_body=ParseInputSerializer,
        responses={200: ParseOutputSerializer},
        operation_description="Analyse un texte libre (FR) et retourne species/breed/symptoms."
    )
    def post(self, request):
        ser = ParseInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user_text = ser.validated_data["text"]

        raw = None
        # 1) Tentative IA -> JSON strict
        try:
            raw = LLMClient.generate_json(SYSTEM_JSON_EXTRACTOR, build_parse_prompt(user_text))
        except Exception as e:
            _log_error(ErrorLog.TYPE_LLM_ERROR, message="parse_generate_failed", payload={"detail": str(e)})

        # 2) Si IA KO -> fallback déterministe
        if raw is None:
            data = _fallback_extract(user_text)
        else:
            data = self._normalize_parse_output(raw)

        # 3) mapping codes → référentiel interne
        cleaned = []
        known_codes = set(Symptom.objects.values_list("code", flat=True))
        unknowns = []
        for s in data.get("symptoms", []):
            code = _map_symptom_code(s.get("code"))
            if code in known_codes:
                item = {"code": code}
                if "duration_days" in s and isinstance(s["duration_days"], (int, float)):
                    item["duration_days"] = int(s["duration_days"])
                if "severity" in s:
                    item["severity"] = str(s["severity"])
                cleaned.append(item)
            else:
                if code:
                    unknowns.append(code)

        if unknowns:
            _log_error(ErrorLog.TYPE_UNKNOWN_SYMPTOM, message="unknown_codes_in_parse", payload={"codes": unknowns})

        out = {
            "species": data.get("species") or "unknown",
            "breed": data.get("breed") or "",
            "symptoms": cleaned
        }
        out_ser = ParseOutputSerializer(data=out)
        out_ser.is_valid(raise_exception=True)
        return Response(out_ser.data, status=status.HTTP_200_OK)

    @staticmethod
    def _normalize_parse_output(raw):
        # Si OK complet
        if isinstance(raw, dict) and {"species", "breed", "symptoms"} <= set(raw.keys()):
            species = str(raw.get("species") or "unknown").lower()
            breed = str(raw.get("breed") or "")
            symptoms = raw.get("symptoms") or []
            if not isinstance(symptoms, list):
                symptoms = []
            return {"species": species, "breed": breed, "symptoms": symptoms}

        # Un seul objet symptôme
        if isinstance(raw, dict) and "code" in raw:
            return {"species": "unknown", "breed": "", "symptoms": [raw]}

        # Liste de symptômes
        if isinstance(raw, list) and all(isinstance(x, dict) and "code" in x for x in raw):
            return {"species": "unknown", "breed": "", "symptoms": raw}

        # sinon vide
        _log_error(ErrorLog.TYPE_NON_JSON, message="parse_output_unexpected", payload={"raw": raw})
        return {"species": "unknown", "breed": "", "symptoms": []}


class TriageView(APIView):
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        request_body=TriageInputSerializer,
        responses={200: TriageOutputSerializer},
        operation_description="Calcule un triage (low/medium/high) + hypothèses + conseils."
    )
    def post(self, request):
        ser = TriageInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        species_code = ser.validated_data["species"]
        breed_name = ser.validated_data.get("breed", "")
        symptom_codes = [(_map_symptom_code(c)) for c in ser.validated_data["symptoms"]]

        # 1) scoring
        probs, meta = score_case(species_code, symptom_codes)
        diseases_qs = Disease.objects.filter(species__code=species_code)\
            .prefetch_related("red_flags", "symptom_links", "symptom_links__symptom")

        triage, top = decide_triage(probs, meta)

        id_to_obj = {d.id: d for d in diseases_qs}
        differential = []
        red_flags = []
        for dis_id, p in top:
            d = id_to_obj.get(dis_id)
            if not d:
                continue
            differential.append({
                "disease": d.name,
                "prob": round(p, 3),
                "why": meta[dis_id].get("why", "")
            })
            red_flags += [rf.text for rf in d.red_flags.all()]
        red_flags = list(dict.fromkeys(red_flags))[:6]

        # 3) conseil par défaut
        advice = "Donnez de l’eau en petites quantités, observez 6–12h. Consultez si des signaux d’alerte apparaissent."

        # 4) reformulation IA (facultatif)
        try:
            expl = LLMClient.generate(
                SYSTEM_TRIAGE,
                build_explain_prompt(species_code, breed_name, differential, red_flags, advice),
                max_tokens=220, temperature=0.0
            )
            if expl and len(expl) < 1200:
                advice = expl
        except Exception as e:
            _log_error(ErrorLog.TYPE_LLM_ERROR, message="triage_explain_failed", payload={"detail": str(e)})

        # 5) clause légale
        advice = _append_legal_disclaimer(advice)

        # 6) sauvegarde du case
        species_obj = Species.objects.filter(code=species_code).first()
        case = Case.objects.create(
            species=species_obj,
            breed=None,  # résolution de breed facultative
            user_text="",
            extracted_symptoms=[],
            symptom_codes=symptom_codes,
            triage=triage,
            differential=differential,
            advice=advice,
            model_trace={
                "engine": "ollama" if getattr(settings, "LLM_PROVIDER", "ollama") != "transformers" else "hf",
                "model": getattr(settings, "OLLAMA_MODEL", "unknown")
            }
        )

        out = TriageOutputSerializer({
            "triage": triage,
            "differential": differential,
            "red_flags": red_flags,
            "advice": advice
        }).data
        return Response(out, status=status.HTTP_200_OK)


# --------- Listes utilitaires ---------

class SpeciesListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        data = list(Species.objects.values("code", "name").order_by("name"))
        return Response(SpeciesSerializer(data, many=True).data)


class BreedListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        sp = request.query_params.get("species", "").strip().lower()
        qs = Breed.objects.all()
        if sp:
            qs = qs.filter(species__code=sp)
        data = list(qs.values("id", "name").order_by("name"))
        return Response(BreedSerializer(data, many=True).data)


class SymptomListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        data = list(Symptom.objects.values("code", "label").order_by("label"))
        return Response(SymptomSerializer(data, many=True).data)


class DiseaseBySpeciesView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        sp = request.query_params.get("species", "").strip().lower()
        qs = Disease.objects.all()
        if sp:
            qs = qs.filter(species__code=sp)
        data = list(qs.values("id", "name", "code", "prevalence").order_by("name"))
        return Response(DiseaseDebugSerializer(data, many=True).data)


# --------- Feedback & Stats ---------

class FeedbackView(APIView):
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        request_body=FeedbackInputSerializer,
        responses={201: FeedbackOutputSerializer},
        operation_description="Enregistre un feedback utilisateur/vétérinaire sur un case."
    )
    def post(self, request):
        ser = FeedbackInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        case_id = ser.validated_data["case_id"]

        case = Case.objects.filter(id=case_id).first()
        if not case:
            return Response({"detail": "Case introuvable."}, status=status.HTTP_404_NOT_FOUND)

        Feedback.objects.create(
            case=case,
            useful=ser.validated_data.get("useful", None),
            validated_diagnosis=ser.validated_data.get("validated_diagnosis", "") or "",
            by_vet=bool(ser.validated_data.get("by_vet", False)),
            note=ser.validated_data.get("note", "") or ""
        )

        out = FeedbackOutputSerializer({"status": "ok", "message": "Feedback enregistré."}).data
        return Response(out, status=status.HTTP_201_CREATED)


class StatsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        now = timezone.now()
        since = now - timedelta(days=30)

        qs = Case.objects.filter(created_at__gte=since)

        total_cases = qs.count()

        # cas par jour
        per_day = defaultdict(int)
        for c in qs.values_list("created_at", flat=True):
            day = c.date().isoformat()
            per_day[day] += 1
        cases_per_day = [{"day": k, "count": v} for k, v in sorted(per_day.items())]

        # top symptômes (à partir de symptom_codes)
        sym_counter = Counter()
        for codes in qs.values_list("symptom_codes", flat=True):
            if isinstance(codes, list):
                sym_counter.update(codes)
        top_symptoms = [{"code": code, "count": cnt} for code, cnt in sym_counter.most_common(10)]

        # top maladies proposées (on prend le disease du premier élément de differential s’il existe)
        dis_counter = Counter()
        for diff in qs.values_list("differential", flat=True):
            if isinstance(diff, list) and diff:
                name = diff[0].get("disease")
                if name:
                    dis_counter[name] += 1
        top_diseases = [{"name": name, "count": cnt} for name, cnt in dis_counter.most_common(10)]

        # taux d’utilité dans les feedbacks
        fb_total = Feedback.objects.filter(case__in=qs).count()
        fb_useful = Feedback.objects.filter(case__in=qs, useful=True).count()
        feedback_useful_rate = (fb_useful / fb_total) if fb_total else 0.0

        out = StatsOutputSerializer({
            "total_cases": total_cases,
            "cases_per_day": cases_per_day,
            "top_symptoms": top_symptoms,
            "top_diseases": top_diseases,
            "feedback_useful_rate": round(feedback_useful_rate, 3),
        }).data
        return Response(out, status=status.HTTP_200_OK)
