## Étape 0 — Cadrage

**Objectif** : Bien définir le périmètre du chatbot vétérinaire.

* Identifier les données minimales à gérer (espèces = chien/chat, \~40 symptômes, \~40–50 maladies).
* Fixer les règles de triage : *low / medium / high*, avec des red flags.
* Préparer un README qui décrit ce que le MVP doit savoir faire.

---

## Étape 1 — Schéma de données (Django)

**Objectif** : Créer la structure pour stocker les infos médicales.

* Créer une app `vetbot/`.
* Modèles : `Species`, `Breed`, `Symptom`, `Disease`, `DiseaseSymptom`, `DiseaseRedFlag`, `Case`, `Feedback`.
* Migration et admin pour pouvoir gérer ces données.

---

## Étape 2 — Données de base (seed)

**Objectif** : Remplir la base pour pouvoir tester rapidement.

* Créer un dossier `vetbot/data/` avec des fichiers JSON : espèces, races, symptômes, maladies.
* Écrire une commande `seed_vetbot` pour importer ces données.
* Vérifier que dans l’admin, tu as déjà des maladies avec symptômes et red flags.

---

## Étape 3 — Intégration du modèle LLM

**Objectif** : Permettre à Django d’appeler le modèle open-source **Llama3-OpenBioLLM-8B** via Ollama (ou Transformers).

* Créer `vetbot/llm/client.py` pour centraliser les appels au modèle.
* Créer `vetbot/llm/prompts.py` pour gérer les instructions données à l’IA.
* Ajouter l’endpoint `/parse` : il prend un texte utilisateur et renvoie `{species, breed, symptoms[...]}` en JSON.
* Tester avec un exemple : ça marche, tu récupères bien les symptômes extraits du texte.

---

## Étape 4 — Scoring déterministe & triage

**Objectif** : Donner une réponse médicale simplifiée à partir des symptômes.

* Écrire une logique de scoring qui compare les symptômes extraits avec la base des maladies (`DiseaseSymptom`).
* Calculer un top-3 de maladies probables avec un score/probabilité.
* Déterminer le niveau de triage (low/medium/high) selon les red flags et les scores.
* Créer l’endpoint `/triage` qui renvoie :

  ```json
  {
    "triage": "medium",
    "differential": [
      {"disease": "Gastro-entérite", "prob": 0.45, "why": "..."},
      {"disease": "Pancréatite", "prob": 0.30, "why": "..."},
      {"disease": "Corps étranger digestif", "prob": 0.20, "why": "..."}
    ],
    "red_flags": ["Vomissements persistants", "Déshydratation"],
    "advice": "Explication simple pour l’utilisateur"
  }
  ```

---

## Étape 5 — Feedback utilisateur

**Objectif** : Améliorer le chatbot grâce aux retours.

* Créer l’endpoint `/feedback` pour stocker : “utile / pas utile”, diagnostic confirmé, note du vétérinaire.
* Lier chaque feedback à un `Case`.

---

## Étape 6 — Intégration Flutter (mobile)

**Objectif** : Permettre aux clients d’utiliser le chatbot depuis l’app.

* Écran 1 : saisie texte (ou choix guidé).
* Écran 2 : affichage résultat (triage, top-3 maladies, conseils).
* Écran 3 : formulaire de feedback.
* Appels API : `/parse`, `/triage`, `/feedback`.

---

## Étape 7 — Observabilité et sécurité

**Objectif** : Fiabilité et conformité.

* Ajouter un disclaimer (“Ce n’est pas un diagnostic, consultez un vétérinaire…”).
* Logger tous les cas pour audit.
* RGPD : anonymiser les données sensibles.
* Ajouter des métriques simples (taux de cas *high*, % feedback utiles…).

---

## Étape 8 — Déploiement

**Objectif** : Mettre en ligne un chatbot fonctionnel.

* Conteneurisation (Docker).
* Déploiement sur Render / Railway.
* Variables d’environnement pour configurer Ollama/HF, DB, email.
* Vérification avec l’app mobile en production.
