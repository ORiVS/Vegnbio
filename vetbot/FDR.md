


But : petit **assistant triage vétérinaire** (“bot”) pour transformer un texte libre en entités (espèce, race, symptômes) puis **estimer l’urgence** et proposer un **différentiel** + **conseils**.

* Endpoints exposés :

  * `POST /api/vetbot/parse/` → NER “léger” (extraction)
  * `POST /api/vetbot/triage/` → triage (low/medium/high) + différentiel + red flags + conseil
* Moteur : règles + mini base de connaissances (`vetbot/logic/knowledge.py`) + un client LLM optionnel (`vetbot/llm/client.py`) **piloté par tes variables d’env** que tu as déjà dans `settings.py` (`LLM_PROVIDER`, `HF_MODEL`, `OLLAMA_MODEL`, etc.).
* Modèles présents (non exposés en API dans les urls) : `Symptom`, `Condition`, `Breed`, `Case` — utiles pour back-office & historiques.
* Sérialiseurs (vérifiés dans `vetbot/serializers.py`) : très **simples et stricts** → ça facilite les tests Postman/Swagger.

---

# Endpoints (prêts Postman)

Base path (d’après ton `config/urls.py`) :
`/api/vetbot/`

## 1) Parser le texte — `POST /parse/`

Extrait **species**, **breed**, **symptoms** (listes d’objets) à partir d’un texte libre.

### Body (JSON)

```json
{
  "text": "Mon chat européen vomit depuis 2 jours et ne mange plus"
}
```

### Réponse (200)

```json
{
  "species": "cat",
  "breed": "European Shorthair",
  "symptoms": [
    {"name": "vomiting"},
    {"name": "anorexia"},
    {"name": "lethargy"}
  ]
}
```

* Schéma exact (vu dans `ParseOutputSerializer`) :

  * `species`: string
  * `breed`: string (peut être vide selon extraction)
  * `symptoms`: **List[Dict]** (chaque dict porte au moins un `name`)

> La logique d’extraction utilise `vetbot/logic/triage.py` + `knowledge.py` (synonymes, mapping espèces/races/symptômes).

---

## 2) Triage — `POST /triage/`

Calcule l’urgence (low/medium/high), propose un **différentiel** et des **red_flags** + **advice**.

### Body (JSON)

```json
{
  "species": "cat",
  "breed": "European Shorthair",
  "symptoms": ["vomiting", "anorexia"]
}
```

> `TriageInputSerializer` est **minimal** : `species` (str), `breed` (str, facultatif), `symptoms` (List[str]).

### Réponse (200)

```json
{
  "triage": "medium",
  "differential": [
    {"condition": "Gastroenteritis", "risk": 0.62},
    {"condition": "Foreign body",    "risk": 0.28}
  ],
  "red_flags": ["persistent vomiting >24h"],
  "advice": "Hydratez, surveillez; consultez si aggravation, déshydratation ou douleur."
}
```

* Schéma (vu dans `TriageOutputSerializer`) :

  * `triage`: `"low" | "medium" | "high"`
  * `differential`: `List[Dict]` (par ex. `{condition, risk}`)
  * `red_flags`: `List[str]`
  * `advice`: `str`

> La pondération vient de `logic/scoring.py` + règles/flags de `logic/triage.py`.
> Si `LLM_PROVIDER` est configuré, la **raisonnement/expansion d’entités** peut s’appuyer sur `vetbot/llm/client.py` (HuggingFace/OLLAMA).

# Bonnes pratiques & extensions

* **Sécurité / Disclaimer** : ajoute un bandeau “*Cet outil n’est pas un diagnostic vétérinaire*…”.
* **Auth** : si tu veux **tracer des cas** par utilisateur, mets `IsAuthenticated` sur `/triage/` et enregistre un `Case` (espèce, symptômes, sortie triage).
* **Enrichir le schéma** : tu peux facilement étendre `TriageInputSerializer` (âge, poids, durée, contexte). La logique (`logic/triage.py`) est déjà structurée pour absorber plus de signaux.
* **Seed Admin** : tu peux remplir `Symptom`, `Condition`, `Breed` avec les données de `logic/knowledge.py` (petit script de management si besoin).

---

Si tu veux, je te file ensuite un **script de management** pour “seeder” les tables (`Symptom`, `Condition`, `Breed`) depuis `knowledge.py`, ou je te prépare la **doc narrative par rôle** (ex. *Public* vs *Véto interne/Admin contenu*).
