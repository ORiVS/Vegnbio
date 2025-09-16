from typing import List, Dict, Any
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Species, Breed, Symptom, Disease, DiseaseSymptom, DiseaseBreedRisk,
    Consultation, Feedback, ReportEvent
)
from .serializers import (
    SymptomSerializer, BreedSerializer,
    AskInputSerializer, AskResponseSerializer, DiseaseShortSerializer, PredictionSerializer,
    FeedbackSerializer, ReportEventSerializer
)

CRITICAL_SYMPTOMS = {"seizure", "bleeding", "poisoning"}  # à étendre si besoin

# ── Autocomplétion symptômes ───────────────────────────────────────────────
class SymptomsView(generics.ListAPIView):
    serializer_class = SymptomSerializer

    def get_queryset(self):
        q = self.request.query_params.get("q","").strip()
        qs = Symptom.objects.all().order_by("label")
        if q:
            qs = qs.filter(Q(label__icontains=q) | Q(code__icontains=q))
        return qs[:50]

# ── Autocomplétion races ───────────────────────────────────────────────────
class BreedsView(generics.ListAPIView):
    serializer_class = BreedSerializer

    def get_queryset(self):
        species_code = self.request.query_params.get("species","").strip()
        q = self.request.query_params.get("q","").strip()
        try:
            sp = Species.objects.get(code=species_code)
        except Species.DoesNotExist:
            return Breed.objects.none()
        qs = Breed.objects.filter(species=sp).order_by("name")
        if q:
            qs = qs.filter(name__icontains=q)
        return qs[:50]

# ── Chatbot ASK ────────────────────────────────────────────────────────────
class AskView(APIView):
    def post(self, request):
        ser = AskInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        species_code = ser.validated_data["species"]
        breed_id = ser.validated_data.get("breed_id")
        input_symptoms: List[str] = [s.strip() for s in ser.validated_data["symptoms"] if s.strip()]

        # species & breed
        try:
            sp = Species.objects.get(code=species_code)
        except Species.DoesNotExist:
            return Response({"detail":"Unknown species"}, status=400)
        breed = None
        if breed_id:
            try:
                breed = Breed.objects.get(id=breed_id, species=sp)
            except Breed.DoesNotExist:
                return Response({"detail":"Breed not found for given species"}, status=400)

        # candidats = maladies de l'espèce
        diseases = Disease.objects.filter(species=sp).distinct()

        preds = []
        for d in diseases:
            # must / nice sets
            must_codes = set(
                DiseaseSymptom.objects.filter(disease=d, kind="MUST")
                .select_related("symptom").values_list("symptom__code", flat=True)
            )
            nice_codes = set(
                DiseaseSymptom.objects.filter(disease=d, kind="NICE")
                .select_related("symptom").values_list("symptom__code", flat=True)
            )

            # must_have : tous présents ?
            if must_codes and not must_codes.issubset(input_symptoms):
                continue  # score 0, on ne retient pas

            # score de base
            base = 0.7
            # bonus
            total_bonus = len(nice_codes)
            found_bonus = len(nice_codes.intersection(input_symptoms)) if total_bonus else 0
            bonus_ratio = (found_bonus / total_bonus) if total_bonus else 0.0
            score = base + 0.3 * bonus_ratio  # ∈ [0.7 ; 1.0]

            # multiplicateur race
            if breed:
                risk = DiseaseBreedRisk.objects.filter(disease=d, breed=breed).first()
                weight = risk.weight if risk else 0.0  # ex: 0.1 => +10%
                score = max(0.0, min(1.0, score * (1.0 + weight)))

            # triage
            triage = "low"
            if d.severity == "high" or CRITICAL_SYMPTOMS.intersection(input_symptoms):
                triage = "high"
            elif score >= 0.5:
                triage = "medium"

            preds.append({
                "disease": d,
                "score": round(float(score), 2),
                "triage": triage,
            })

        # trier par score et garder top-3 (ou vide si aucun must ne match)
        preds = sorted(preds, key=lambda x: x["score"], reverse=True)[:3]

        # sauvegarder consultation
        cons = Consultation.objects.create(
            user=request.user if request.user and request.user.is_authenticated else None,
            species=sp,
            breed=breed,
            input_symptoms=input_symptoms,
            predictions=[{
                "disease_id": p["disease"].id,
                "name": p["disease"].name,
                "score": p["score"],
                "triage": p["triage"],
            } for p in preds]
        )

        # réponse
        data = {
            "predictions": [{
                "disease": {"id": p["disease"].id, "name": p["disease"].name},
                "score": p["score"],
                "triage": p["triage"],
            } for p in preds],
            "advice": "Ce résultat est indicatif et ne remplace pas un avis vétérinaire.",
            "consultation_id": cons.id
        }
        return Response(data, status=200)

# ── Feedback ────────────────────────────────────────────────────────────────
class FeedbackView(APIView):
    def post(self, request):
        ser = FeedbackSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        cid = ser.validated_data["consultation_id"]
        is_useful = ser.validated_data["is_useful"]
        notes = ser.validated_data.get("notes","")
        chosen_id = ser.validated_data.get("chosen_diagnosis_id")

        try:
            cons = Consultation.objects.get(id=cid)
        except Consultation.DoesNotExist:
            return Response({"detail":"Consultation not found"}, status=400)

        chosen = None
        if chosen_id:
            try:
                chosen = Disease.objects.get(id=chosen_id)
            except Disease.DoesNotExist:
                return Response({"detail":"chosen_diagnosis_id invalid"}, status=400)

        Feedback.objects.create(
            consultation=cons,
            is_useful=is_useful,
            notes=notes,
            chosen_diagnosis=chosen
        )
        return Response({"ok": True}, status=200)

# ── Reporting (remontée d'erreurs / signalements) ───────────────────────────
class ReportEventView(APIView):
    def post(self, request):
        ser = ReportEventSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        v = ser.validated_data

        cons = None
        if v.get("consultation_id"):
            cons = Consultation.objects.filter(id=v["consultation_id"]).first()

        evt = ReportEvent.objects.create(
            user=request.user if request.user and request.user.is_authenticated else None,
            source=v.get("source", "mobile"),
            event_type=v["event_type"],
            category=v["category"],
            message=v.get("message",""),
            context_json=v.get("context", {}),
            consultation=cons,
            endpoint=v.get("endpoint",""),
            http_status=v.get("http_status"),
            request_id=v.get("request_id",""),
        )
        return Response({"ok": True, "event_id": evt.id}, status=201)

class ReportingSummaryView(APIView):
    def get(self, request):
        data = {
            "total": ReportEvent.objects.count(),
            "by_category": dict(
                ReportEvent.objects.values_list("category")
                .order_by().annotate(n=models.Count("id"))
                .values_list("category","n")
            ),
        }
        return Response(data, status=200)
