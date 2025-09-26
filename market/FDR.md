* Base path : `/api/market/`
* Auth (JWT Bearer) : `Authorization: Bearer <access_token>`
* Décimaux (Swagger) : envoyez `price`, `min_order_qty`, `stock_qty` **en string** (`"4.20"`) sauf si vous avez désactivé la coercition côté DRF.

---

# Offres fournisseur (SupplierOffer)

## 1) Lister les offres publiques

**GET** `/offers/`
**Acteurs** : Public (anonyme ou connecté)
**Auth** : facultative
**Query params** :

* `q`, `is_bio=true|false`, `region`
* `allergen=GLUTEN,SESAME`, `exclude_allergens=...`
* `available_on=YYYY-MM-DD`
* `sort=price|-price`
  **Body** : —

---

## 2) Créer une offre

**POST** `/offers/`
**Acteurs** : **FOURNISSEUR** uniquement (profil region ∈ REGIONS_ALLOWED)
**Auth** : requise
**Body (JSON)** :

```json
{
  "product_name": "Tomates cœur de bœuf",
  "description": "Variété ancienne",
  "is_bio": true,
  "producer_name": "Ferme des Lilas",
  "region": "Île-de-France",
  "allergens": [1, 3],
  "unit": "kg",
  "price": "4.20",
  "min_order_qty": "5",
  "stock_qty": "120",
  "available_from": "2025-10-01",
  "available_to": "2025-12-15"
}
```

**Notes** : `is_bio` doit être `true`; limites hebdo (5/7j).

---

## 3) Consulter une offre

**GET** `/offers/{id}/`
**Acteurs** : Public (anonyme ou connecté)
**Auth** : facultative
**Visibilité** : non-propriétaires ne voient que **PUBLISHED**
**Body** : —

---

## 4) Mettre à jour une offre

**PATCH/PUT** `/offers/{id}/`
**Acteurs** : **FOURNISSEUR** **propriétaire** de l’offre
**Auth** : requise
**Body (JSON)** : mêmes champs que création (tous optionnels en PATCH, tous en PUT).

---

## 5) Supprimer une offre

**DELETE** `/offers/{id}/`
**Acteurs** : **FOURNISSEUR** **propriétaire**
**Auth** : requise
**Body** : —

---

## 6) Publier une offre

**POST** `/offers/{id}/publish/`
**Acteurs** : **FOURNISSEUR** **propriétaire**
**Auth** : requise
**Body** : —
**Effet** : `status = "PUBLISHED"` (validation modèle exécutée)

---

## 7) Retirer une offre (unlist)

**POST** `/offers/{id}/unlist/`
**Acteurs** : **FOURNISSEUR** **propriétaire**
**Auth** : requise
**Body** : —
**Effet** : `status = "UNLISTED"`

---

## 8) Repasser en brouillon

**POST** `/offers/{id}/draft/`
**Acteurs** : **FOURNISSEUR** **propriétaire**
**Auth** : requise
**Body** : —
**Effet** : `status = "DRAFT"`

---

## 9) Comparer plusieurs offres

**GET** `/offers/compare/?ids=1,2,3`
**Acteurs** : Public (anonyme ou connecté)
**Auth** : facultative
**Body** : —

---

## 10) Importer une offre en Product (Menu)

**POST** `/offers/{id}/import_to_product/`
**Acteurs** : **RESTAURATEUR**
**Auth** : requise
**Body** : —
**Effet** : crée `menu.Product` depuis l’offre (+ allers).
**Réponse** : `{ "status": "imported", "product_id": <id> }`

---

## 11) Signaler une offre (flag)

**POST** `/offers/{id}/flag/`
**Acteurs** : **tout utilisateur authentifié**, **sauf** le **FOURNISSEUR propriétaire**
**Auth** : requise
**Body (JSON)** :

```json
{ "reason": "Prix anormal", "details": "Semble abusif vs marché" }
```

**Effet** : crée un `OfferReport`, `status="FLAGGED"`, email au fournisseur.

---

## 12) Modérer le statut d’une offre

**POST** `/offers/{id}/moderate_status/`
**Acteurs** : **ADMIN**
**Auth** : requise
**Body (JSON)** :

```json
{ "status": "PUBLISHED" }  // ou "UNLISTED" / "DRAFT"
```

---

# Notes / évaluations (OfferReview)

## 13) Lister les reviews

**GET** `/reviews/`
**Acteurs** : Public (anonyme ou connecté)
**Auth** : facultative
**Query** : `?offer=<id>` (optionnel)
**Body** : —

---

## 14) Créer une review

**POST** `/reviews/`
**Acteurs** : **RESTAURATEUR** ou **ADMIN**
**Auth** : requise
**Body (JSON)** :

```json
{ "offer": 12, "rating": 5, "comment": "Top qualité" }
```

**Règles** : `rating ∈ [1..5]`, unique par (offer, author).

---

## 15) Consulter / éditer / supprimer une review

**GET/PUT/PATCH/DELETE** `/reviews/{id}/`
**Acteurs** :

* GET : Public
* PUT/PATCH/DELETE : utilisateur a qui appartenant l'offre **authentifié** —  permission d’objet*
  **Auth** : requise pour modifier/supprimer
  **Body** : en PUT/PATCH, même schéma que création (rating/comment).

---

# Signalements (OfferReport)

## 16) Lister les signalements

**GET** `/reports/`
**Acteurs** : Public (anonyme ou connecté)
**Auth** : facultative
**Body** : —

---

## 17) Créer un signalement

**POST** `/reports/`
**Acteurs** : **tout utilisateur authentifié**
**Auth** : requise
**Body (JSON)** :

```json
{ "offer": 12, "reason": "Fraude", "details": "Certif bio douteuse" }
```

---

## 18) Modérer un signalement

**POST** `/reports/{id}/moderate/`
**Acteurs** : **ADMIN**
**Auth** : requise
**Body (JSON)** :

```json
{ "action": "REVIEWED" }    // ou "ACTION_TAKEN"
```

---

# Commentaires (OfferComment)

## 19) Lister les commentaires

**GET** `/comments/`
**Acteurs** : Public (anonyme ou connecté)
**Auth** : facultative
**Filtrage** : `?offer=<id>` optionnel
**Visibilité** : seuls `is_public=true`; **ADMIN** voient tout
**Body** : —

---

## 20) Créer un commentaire

**POST** `/comments/`
**Acteurs** : **tout utilisateur authentifié**
**Auth** : requise
**Body (JSON)** :

```json
{ "offer": 12, "content": "Intéressé par 20 kg/semaine", "is_public": true }
```

**Règle** : `content` non vide.

---

## 21) Éditer un commentaire

**PUT/PATCH** `/comments/{id}/`
**Acteurs** : **auteur** du commentaire **ou ADMIN**
**Auth** : requise
**Body (JSON)** : mêmes champs que création (typiquement `content`, `is_public`)
**Effet** : `is_edited=true` automatiquement.

---

## 22) Supprimer un commentaire

**DELETE** `/comments/{id}/`
**Acteurs** : **auteur** du commentaire **ou ADMIN**
**Auth** : requise
**Body** : —

---

## Récap express des acteurs par action

* **Public (anonyme)** : `GET /offers/`, `GET /offers/{id}/` (publisées), `GET /offers/compare/`, `GET /reviews/`, `GET /reports/`, `GET /comments/` (publics).
* **FOURNISSEUR** (owner) : créer/éditer/supprimer **ses** offres, `publish/`, `unlist/`, `draft/`.
* **RESTAURATEUR** : `POST /reviews/`, `POST /offers/{id}/import_to_product/`.
* **Utilisateurs authentifiés** (tous rôles sauf exception) : `POST /offers/{id}/flag/`, `POST /comments/`, édition/suppression de **leurs** commentaires.
* **ADMIN** : `POST /offers/{id}/moderate_status/`, `POST /reports/{id}/moderate/`, voit **tous** les commentaires (public/privé), peut éditer/supprimer n’importe quel commentaire.

