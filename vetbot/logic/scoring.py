# vetbot/logic/scoring.py
import math
from typing import Dict, List, Tuple
from vetbot.models import Species, Symptom, Disease

def _softmax(scores: Dict[int, float]) -> Dict[int, float]:
    if not scores:
        return {}
    m = max(scores.values())
    exps = {k: math.exp(v - m) for k, v in scores.items()}
    s = sum(exps.values())
    return {k: (exps[k] / s) for k in scores}

def score_case(species_code: str, symptom_codes: List[str]) -> Tuple[Dict[int, float], Dict[int, Dict]]:
    """
    Retourne:
      - probs: { disease_id: prob }
      - meta : { disease_id: {"score": float, "why": str, "has_critical": bool} }
    """
    try:
        species = Species.objects.get(code=species_code)
    except Species.DoesNotExist:
        return {}, {}

    sym_map = {s.code: s.id for s in Symptom.objects.filter(code__in=symptom_codes)}
    present_ids = set(sym_map.values())

    scores: Dict[int, float] = {}
    meta: Dict[int, Dict] = {}

    qs = Disease.objects.filter(species=species)\
        .prefetch_related("symptom_links", "red_flags", "symptom_links__symptom")

    for dis in qs:
        sc = 0.0
        why_bits = []
        has_critical = False

        for link in dis.symptom_links.all():
            if link.symptom_id in present_ids:
                sc += link.weight
                why_bits.append(f"+{link.symptom.code}(w={link.weight})")
                if link.critical:
                    has_critical = True
            else:
                if link.critical:
                    sc -= 0.3
                    why_bits.append(f"-{link.symptom.code}(critique manquant)")

        # petit bonus de "prévalence" (facultatif)
        sc += float(dis.prevalence or 0.0) * 0.2

        scores[dis.id] = sc
        meta[dis.id] = {
            "score": sc,
            "why": "; ".join(why_bits)[:500],
            "has_critical": has_critical
        }

    probs = _softmax(scores)
    return probs, meta

def decide_triage(probs, meta):
    if not probs:
        return "low", []
    top = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)[:3]
    triage = "low"

    # au moins medium si un symptôme "critical" est présent dans le top
    if any(meta[d_id].get("has_critical") for d_id, _ in top):
        triage = "medium"

    # ⚠️ prudence : si la proba du top1 est élevée, on monte à medium
    if top and top[0][1] >= 0.40:
        triage = "medium"

    # high si le #1 est "critical" ET proba haute
    if top and meta[top[0][0]].get("has_critical") and top[0][1] >= 0.45:
        triage = "high"

    return triage, top
