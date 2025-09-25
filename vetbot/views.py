from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Symptom
from .serializers import ParseInputSerializer, ParseOutputSerializer
from vetbot.llm.client import LLMClient
from vetbot.llm.prompts import SYSTEM_JSON_EXTRACTOR, build_parse_prompt

from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .serializers import TriageInputSerializer, TriageOutputSerializer
from .logic.scoring import score_case, decide_triage
from .models import Disease, Case
from .llm.client import LLMClient
from .llm.prompts import SYSTEM_TRIAGE, build_explain_prompt


SYM_ALIAS = {
    # Aliases utiles si le modèle renvoie des libellés en français
    "vomissements": "vomiting",
    "fièvre": "fever",
    "apathie": "lethargy",
    "fatigue": "lethargy",
    "toux": "cough",
    "éternuements": "sneezing",
    # ajoute au fur et à mesure...
}

def _map_symptom_code(code: str) -> str:
    c = (code or "").strip().lower()
    return SYM_ALIAS.get(c, c)

class ParseView(APIView):
    def post(self, request):
        ser = ParseInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        text = ser.validated_data["text"]

        raw = LLMClient.generate_json(SYSTEM_JSON_EXTRACTOR, build_parse_prompt(text))
        data = _normalize_parse_output(raw, text)

        # mapping codes → référentiel interne
        cleaned = []
        known_codes = set(Symptom.objects.values_list("code", flat=True))
        for s in data.get("symptoms", []):
            code = _map_symptom_code(s.get("code"))
            if code in known_codes:
                item = {"code": code}
                if "duration_days" in s and isinstance(s["duration_days"], (int, float)):
                    item["duration_days"] = int(s["duration_days"])
                if "severity" in s:
                    item["severity"] = str(s["severity"])
                cleaned.append(item)

        # valeurs par défaut si le modèle n'a rien trouvé
        species = data.get("species") or "unknown"
        breed = data.get("breed") or ""

        out = {
            "species": species,
            "breed": breed,
            "symptoms": cleaned
        }
        # valider le contrat de sortie
        out_ser = ParseOutputSerializer(data=out)
        out_ser.is_valid(raise_exception=True)
        return Response(out_ser.data, status=status.HTTP_200_OK)

def _normalize_parse_output(raw, user_text: str):
    """
    Garantit un dict avec keys: species (str), breed (str), symptoms (list[dict]).
    Convertit les sorties partielles (ex: un seul objet symptôme) en structure complète.
    """
    # Si le modèle a renvoyé directement la structure complète
    if isinstance(raw, dict) and {"species","breed","symptoms"} <= set(raw.keys()):
        # ménage minimum
        species = str(raw.get("species") or "unknown").lower()
        breed = str(raw.get("breed") or "")
        symptoms = raw.get("symptoms") or []
        if not isinstance(symptoms, list):
            symptoms = []
        return {"species": species, "breed": breed, "symptoms": symptoms}

    # Si le modèle a renvoyé un SEUL objet symptôme (ton cas actuel)
    if isinstance(raw, dict) and "code" in raw:
        return {
            "species": "unknown",
            "breed": "",
            "symptoms": [raw]
        }

    # Si c'est une liste de symptômes
    if isinstance(raw, list) and all(isinstance(x, dict) and "code" in x for x in raw):
        return {
            "species": "unknown",
            "breed": "",
            "symptoms": raw
        }

    # Dernier recours: rien d'exploitable → squelette vide
    return {"species":"unknown", "breed":"", "symptoms":[]}


class TriageView(APIView):
    def post(self, request):
        ser = TriageInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        species = ser.validated_data["species"]
        breed = ser.validated_data.get("breed", "")
        symptoms = ser.validated_data["symptoms"]  # ex: ["vomiting","fever","lethargy"]

        # 1) Scoring déterministe
        probs, meta = score_case(species, symptoms)
        diseases_qs = Disease.objects.filter(species__code=species)\
            .prefetch_related("red_flags", "symptom_links", "symptom_links__symptom")

        triage, top = decide_triage(probs, meta)

        # 2) Construire differential + red flags fusionnés
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
        red_flags = list(dict.fromkeys(red_flags))[:6]  # unique + limite

        # 3) Advice par défaut
        advice = (
            "Donnez de l’eau en petites quantités, observez 6–12h. "
            "Consultez un vétérinaire si des signaux d’alerte apparaissent."
        )

        # 4) Reformulation par le LLM (facultatif; robuste aux erreurs)
        try:
            expl = LLMClient.generate(
                SYSTEM_TRIAGE,
                build_explain_prompt(species, breed, differential, red_flags, advice),
                max_tokens=220, temperature=0.0
            )
            if expl and len(expl) < 1200:
                advice = expl
        except Exception:
            pass

        # 5) Sauvegarde du Case (audit/feedback)
        case = Case.objects.create(
            species=diseases_qs.first().species if diseases_qs.exists() else None,
            breed=None,  # tu pourras faire un resolve sur Breed plus tard
            user_text="",  # si tu viens de /parse, tu peux stocker le texte ici
            extracted_symptoms=[], symptom_codes=symptoms,
            triage=triage, differential=differential, advice=advice,
            model_trace={"engine": "ollama", "model": settings.OLLAMA_MODEL}
        )

        out = TriageOutputSerializer({
            "triage": triage,
            "differential": differential,
            "red_flags": red_flags,
            "advice": advice
        }).data
        return Response(out, status=status.HTTP_200_OK)
