# Purchasing — Parcours “Commande fournisseur”

Ce module permet à un **restaurateur** de passer une commande à un **fournisseur** à partir d’offres publiées, puis au **fournisseur** de confirmer tout ou partie des quantités.
Toutes les routes sont préfixées par **`/api/purchasing/`** via le router : **`/api/purchasing/orders/...`**.
Auth : **JWT Bearer**.

## Règles métier clés

* **Seul un RESTAURATEUR** peut **créer** une commande.
* La commande cible **obligatoirement** un **FOURNISSEUR**.
* Les **lignes** de commande :

  * ne peuvent viser que des **offres publiées** (`status="PUBLISHED"`) du **même fournisseur** ;
  * **produits bio** uniquement, **région** dans `REGIONS_ALLOWED` ;
  * `qty_requested > 0`.
* À la création, le **prix unitaire** de chaque ligne est **figé** depuis l’offre (`unit_price = offer.price`).
* **Revue fournisseur** : confirme partiellement ou totalement les quantités → décrémente le **stock** des offres ; met à jour le **statut** de la commande :

  * toutes les lignes à `0` → `REJECTED`
  * au moins une ligne confirmée `< qty_requested` → `PARTIALLY_CONFIRMED`
  * toutes les lignes confirmées `>= qty_requested` → `CONFIRMED`
* **E-mails** automatisés :

  * à la création : mail au fournisseur “Nouvelle commande à valider”.

---

# Endpoints “Orders”

Base : `/api/purchasing/orders/`

## 1) Lister toutes les commandes (admin)

**GET** `/orders/`
**Acteurs** : **ADMIN** uniquement (sinon 403)
**Auth** : requise
**Body** : —
**Réponse 200** : liste des commandes (avec `items`).

> Note: dans le code, l’action `list` renvoie 403 si `role != ADMIN`.

---

## 2) Créer une commande (restaurateur)

**POST** `/orders/`
**Acteurs** : **RESTAURATEUR**
**Auth** : requise
**Body (JSON)** :

```json
{
  "supplier": 42,
  "note": "Livrer avant vendredi si possible",
  "items": [
    { "offer": 15, "qty_requested": "10.00" },
    { "offer": 17, "qty_requested": "5.0" }
  ]
}
```

**Détails** :

* `supplier` : id utilisateur (FOURNISSEUR) destinataire.
* `items[].offer` : id d’offres **PUBLISHED** du même fournisseur.
* `qty_requested` : **Decimal** (mettre entre guillemets dans Swagger).

**Réponses** :

* `201` : commande créée (`status="PENDING_SUPPLIER"`), items avec `unit_price` copiés depuis les offres.
* `400` : validations (offre non publiée, stock ≤ 0, offre d’un autre fournisseur, quantité ≤ 0…).

**Exemple cURL** :

```bash
curl -X POST https://vegnbio.onrender.com/api/purchasing/orders/ \
 -H "Authorization: Bearer <ACCESS>" -H "Content-Type: application/json" \
 -d '{
   "supplier": 42,
   "note": "Livrer avant vendredi si possible",
   "items": [
     {"offer": 15, "qty_requested": "10"},
     {"offer": 17, "qty_requested": "5.5"}
   ]
 }'
```

---

## 3) Récupérer une commande par id

**GET** `/orders/{id}/`
**Acteurs** : **restaurateur authentifié**
**Auth** : requise
**Body** : —
**Réponse 200** : détail commande + items (nom produit, unité, quantités, prix).

> **Attention** (sécurité/privacité) : dans l’état actuel, *n’importe quel utilisateur authentifié* peut lire une commande par id.
> Recommandation : restreindre la lecture aux **ADMIN**, **restaurateur créateur** ou **fournisseur ciblé** (permission d’objet).

---

## 4) Mettre à jour/supprimer une commande

**PUT/PATCH/DELETE** `/orders/{id}/`
**Acteurs** : **restaurateur authentifié**
**Auth** : requise
**Body** : schéma lecture/écriture par défaut (serializer Read utilisé ici)


---

## 5) Mes commandes côté restaurateur

**GET** `/orders/my_restaurant_orders/`
**Acteurs** : **RESTAURATEUR** (retourne uniquement ses commandes)
**Auth** : requise
**Body** : —
**Réponse 200** : liste.

**Exemple** :

```bash
curl https://vegnbio.onrender.com/api/purchasing/orders/my_restaurant_orders/ \
 -H "Authorization: Bearer <ACCESS>"
```

---

## 6) Boîte de réception côté fournisseur

**GET** `/orders/supplier_inbox/`
**Acteurs** : **FOURNISSEUR** (retourne les commandes qui lui sont adressées)
**Auth** : requise
**Body** : —
**Réponse 200** : liste.

**Exemple** :

```bash
curl https://vegnbio.onrender.com/api/purchasing/orders/supplier_inbox/ \
 -H "Authorization: Bearer <ACCESS>"
```

---

## 7) Revue fournisseur (confirmation des quantités)

**POST** `/orders/{id}/supplier_review/`
**Acteurs** : **FOURNISSEUR** (celui de la commande)
**Auth** : requise
**Body (JSON)** :

```json
{
  "items": [
    { "id": 101, "qty_confirmed": "4.50" },
    { "id": 102, "qty_confirmed": "0" }
  ]
}
```

**Détails** :

* `items[].id` : **id de la ligne de commande** (pas l’id de l’offre).
* `qty_confirmed` : **Decimal** string.
* Contrôles :

  * l’item existe dans **cette** commande ;
  * `qty_confirmed ≥ 0` ;
  * `qty_confirmed ≤ offer.stock_qty`.
* Effets :

  * met à jour `qty_confirmed` de chaque item ;
  * **décrémente** `offer.stock_qty` de la quantité confirmée ;
  * met à jour le **statut** de la commande (`REJECTED` / `PARTIALLY_CONFIRMED` / `CONFIRMED`).

**Réponses** :

* `200` : commande mise à jour (payload lecture complet).
* `400` : validations (id item inconnu, dépassement de stock, quantités < 0…).
* `403` : si l’utilisateur n’est pas le **supplier** de la commande.

**Exemple cURL** :

```bash
curl -X POST https://vegnbio.onrender.com/api/purchasing/orders/57/supplier_review/ \
 -H "Authorization: Bearer <ACCESS>" -H "Content-Type: application/json" \
 -d '{
   "items": [
     {"id": 101, "qty_confirmed": "4.5"},
     {"id": 102, "qty_confirmed": "0"}
   ]
 }'
```

---

## Modèle de données (résumé utile)

* **SupplierOrder**
  `restaurateur (FK User)`, `supplier (FK User)`, `status`, `note`, `created_at`, `confirmed_at`, `items (reverse)`
  Statuts : `PENDING_SUPPLIER`, `CONFIRMED`, `PARTIALLY_CONFIRMED`, `REJECTED`, `CANCELLED`.

* **SupplierOrderItem**
  `order (FK)`, `offer (FK SupplierOffer)`, `qty_requested`, `qty_confirmed?`, `unit_price` (snapshot du prix offre).
  Propriétés d’affichage (serializer read) : `product_name`, `unit`.

---

## Exemples de réponses (lecture)

**GET** `/orders/{id}/` → `200`

```json
{
  "id": 57,
  "restaurateur": 5,
  "supplier": 42,
  "status": "PARTIALLY_CONFIRMED",
  "created_at": "2025-09-26T14:17:00Z",
  "confirmed_at": null,
  "note": "Livrer avant vendredi si possible",
  "items": [
    {
      "id": 101,
      "offer": 15,
      "product_name": "Tomates cœur de bœuf",
      "unit": "kg",
      "qty_requested": "10.00",
      "qty_confirmed": "4.50",
      "unit_price": "4.20"
    },
    {
      "id": 102,
      "offer": 17,
      "product_name": "Courgettes",
      "unit": "kg",
      "qty_requested": "5.50",
      "qty_confirmed": "0.00",
      "unit_price": "2.80"
    }
  ]
}
```

---

## Remarques & améliorations possibles

* **Contrôle d’accès lecture/modif** : aujourd’hui, n’importe quel **authentifié** peut lire/modifier/supprimer une commande par id.
  ➜ Recommandé : permission d’objet (visible par **ADMIN**, **restaurateur=owner**, **supplier**) et blocage des `PUT/PATCH/DELETE` hors cas explicitement autorisés (ex. **annulation** par restaurateur avant revue).
* **Minima de commande** : tu ne vérifies pas `min_order_qty` (offre) vs `qty_requested`. Tu peux l’ajouter dans `SupplierOrderItemCreateSerializer.validate`.
* **confirmed_at** : non renseigné. Tu peux la fixer lors de la transition `CONFIRMED/PARTIALLY_CONFIRMED/REJECTED`.
* **Dispo/stock** : à la création tu refuses `stock_qty <= 0`, mais tu n’empêches pas `qty_requested > stock` (valid/choix produit → la coupe réelle se fait au moment de la revue). C’est cohérent si le fournisseur tranche ; documenté ici.
