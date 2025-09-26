Parfait — voici la **documentation narrative par rôle** pour l’app **Orders** (créneaux, panier, checkout, commandes), en collant exactement à ton code actuel et en rappelant l’intégration fidélité.

---

# Vue d’ensemble

* **Base path** : `/api/orders/`
* **Auth globale** : toutes les routes sont **protégées** → `Authorization: Bearer <access_token>`
* **Modèles clés** :

  * `DeliverySlot` : créneaux (par restaurant). *Gestion surtout via Admin Django dans ton code actuel.*
  * `Cart`, `CartItem` : panier utilisateur (1 panier actif par user).
  * `Order`, `OrderItem` : commande + lignes.
* **Fidélité intégrée au checkout** :

  * Utilisation de points : baisse le total (débit des points).
  * Gain de points : sur le **total payé** (après remise points), en fonction de `LoyaltyProgram.earn_rate_per_euro`.
  * Les taux et la valeur des points proviennent de l’app **fidelite** (configurable dans l’admin).

**Rappel décimaux** : selon la config OpenAPI/DRF, vous pouvez envoyer des décimaux en nombres (`12.90`) ou en strings (`"12.90"`). Ton serializer accepte les `DecimalField` natifs.

---

# RÔLE : CLIENT (utilisateur authentifié)

## 1) Lister les créneaux de livraison

* **GET** `/api/orders/slots/`
* **Body** : —
* **Réponse 200** : tableau de `{ "id", "start", "end" }`.

**Exemple**

```bash
curl https://vegnbio.onrender.com/api/orders/slots/ \
 -H "Authorization: Bearer <ACCESS>"
```

---

## 2) Voir mon panier

* **GET** `/api/orders/cart/`
* **Réponse 200**

```json
{
  "user": 33,
  "items": [
    { "id": 1, "external_item_id": "DISH-123", "name": "Curry", "unit_price": "12.90", "quantity": 2, "line_total": "25.80" }
  ],
  "total": "25.80"
}
```

---

## 3) Ajouter un article au panier

* **POST** `/api/orders/cart/`
* **Body (obligatoire)**

```json
{
  "restaurant_id": 12,
  "external_item_id": "DISH-123",
  "name": "Curry de légumes",
  "unit_price": "12.90",
  "quantity": 2
}
```

* **Règles** :

  * `restaurant_id` est requis (ton code lie chaque item à un restaurant).
  * Si le même `external_item_id` existe déjà **pour ce restaurant** → la quantité est **incrémentée** et le nom/prix mis à jour.
* **Réponse 201**

```json
{ "message": "Ajouté au panier" }
```

**cURL**

```bash
curl -X POST https://vegnbio.onrender.com/api/orders/cart/ \
 -H "Authorization: Bearer <ACCESS>" -H "Content-Type: application/json" \
 -d '{ "restaurant_id":12, "external_item_id":"DISH-123", "name":"Curry de légumes", "unit_price":"12.90", "quantity":2 }'
```

---

## 4) Supprimer un article du panier

* **DELETE** `/api/orders/cart/`
* **Body (legacy minimal)** :

```json
{ "external_item_id": "DISH-123" }
```

* **Body (recommandé, pour éviter ambiguïté entre restos)** :

```json
{ "external_item_id": "DISH-123", "restaurant_id": 12 }
```

* **Réponse 200**

```json
{ "message": "Supprimé" }
```

* **404** si rien ne correspond.

---

## 5) Valider la commande (Checkout) — avec points de fidélité optionnels

* **POST** `/api/orders/checkout/`
* **Body**

```json
{
  "address_line1": "25 Rue Exemple",
  "address_line2": "",
  "city": "Paris",
  "postal_code": "75010",
  "phone": "0600000000",
  "slot_id": 3,
  "points_to_use": 200   // optionnel, ≥ 0
}
```

* **Règles** :

  * Le panier ne doit pas être vide.
  * Tous les items doivent avoir un `restaurant` associé (ton code bloque sinon).
  * `slot_id` doit exister.
  * Si `points_to_use` > solde client → 400.
  * Si `points_to_use` convertis dépassent le subtotal → ajustement automatique au **maximum utile**.
* **Effets** :

  * Crée un `Order` + `OrderItem`(s) (copie du panier).
  * Vide le panier.
  * **Débite** les points utilisés (SPEND).
  * **Crédite** les points gagnés sur `total_paid` (EARN, arrondi bas).
* **Réponse 201** :

```json
{
  "message": "Commande créée",
  "order": {
    "id": 101,
    "status": "PENDING",
    "created_at": "2025-09-26T18:01:23Z",
    "address_line1": "25 Rue Exemple",
    "address_line2": "",
    "city": "Paris",
    "postal_code": "75010",
    "phone": "0600000000",
    "slot": 3,
    "subtotal": "25.80",
    "discount_points_used": 200,
    "discount_euros": "2.00",
    "total_paid": "23.80",
    "items": [
      { "external_item_id": "DISH-123", "name": "Curry de légumes", "unit_price": "12.90", "quantity": 2, "line_total": "25.80" }
    ]
  }
}
```

**cURL**

```bash
curl -X POST https://vegnbio.onrender.com/api/orders/checkout/ \
 -H "Authorization: Bearer <ACCESS>" -H "Content-Type: application/json" \
 -d '{ "address_line1":"25 Rue Exemple","city":"Paris","postal_code":"75010","slot_id":3,"points_to_use":200 }'
```

---

## 6) Lister mes commandes

* **GET** `/api/orders/`
* **Réponse 200** : liste de commandes me concernant.

---

## 7) Consulter le statut d’une de mes commandes

* **GET** `/api/orders/{id}/status/`
* **Réponse 200**

```json
{ "id": 101, "status": "PENDING" }
```

> Ton code filtre ici **par user** (le client ne peut lire que ses statuts).

---

# RÔLE : RESTAURATEUR (ou OPERATIONS)

Dans l’API actuelle :

* Les **créneaux** (`DeliverySlot`) sont exposés en **lecture** via `/slots/` (tout le monde authentifié).
* La **gestion** des créneaux (création/duplication/suppression des passés) se fait **dans l’Admin Django** (fichier `orders/admin.py` complet déjà prêt).
* La mise à jour **du statut** de commande est exposée par `PATCH /api/orders/{id}/status/` (non restreinte par rôle dans le code, à sécuriser si besoin).

## 1) Consulter les créneaux

* **GET** `/api/orders/slots/` (auth requis)

## 2) Mettre à jour le statut d’une commande

* **PATCH** `/api/orders/{id}/status/`
* **Body**

```json
{ "status": "PREPARING" }  // ou OUT_FOR_DELIVERY / DELIVERED / CANCELLED / PENDING
```

* **Réponse 200**

```json
{ "message":"Statut mis à jour", "id": 101, "status":"PREPARING" }
```

> ⚠️ **À sécuriser** si tu veux limiter cette action aux **owners** du restaurant ou aux **admins** (ajoute une permission custom qui vérifie que la commande appartient à un restaurant du restaurateur avant d’autoriser le PATCH).

## 3) Admin Django (recommandé côté resto)

* **DeliverySlotAdmin** : duplication J+1, J+7, suppression créneaux passés.
* **OrderAdmin** : actions “Marquer En préparation / En livraison / Livrée / Annulée”, export CSV, lecture des totaux.
* **CartAdmin** : inspection ponctuelle des paniers (utile support).

---

# RÔLE : ADMIN

* Même capacités que RESTAURATEUR pour suivre/mettre à jour les statuts, mais **à l’échelle globale**.
* **Admin Django** :

  * Gestion des `DeliverySlot` (création globale si besoin).
  * Consultation/exports des `Order` et `OrderItem`.
* **Sécurité** : si tu durcis les permissions du PATCH statut, prévois l’exception ADMIN.

---

# RÈGLES & COMPORTEMENTS CLÉS

* **Panier** :

  * Un **seul** panier par utilisateur (`Cart` OneToOne).
  * Un `CartItem` est **unique** par `(cart, restaurant, external_item_id)`.
* **Décimaux** :

  * DRF accepte les `DecimalField` ; en front Swagger, envoie `12.90` ou `"12.90"`.
* **Fidélité** (rappel) :

  * `points_to_use` convertis en € via `program.redeem_rate_euro_per_point`.
  * **Débit** des points à la création de la commande (SPEND).
  * **Crédit** sur `total_paid` via `program.earn_rate_per_euro` (EARN, arrondi bas).
* **Slots** :

  * L’API ne crée/modifie **pas** les slots (lecture seule) → fais-le côté **Admin Django**.

---