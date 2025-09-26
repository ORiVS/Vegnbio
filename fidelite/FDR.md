# DOCUMENTATION NARRATIVE (par rôle) — FIDÉLITÉ

**Base path** : `/api/fidelite/`
**Auth** : `Authorization: Bearer <access_token>` (tous endpoints sont protégés)

**Modèles clés** :

* `LoyaltyProgram` : configuration globale (1 enregistrement).
* `Membership` : adhésion + solde de points par utilisateur.
* `PointsTransaction` : historique (EARN / SPEND / ADJUST).

**Paramétrage recommandé (via Admin Django)** :

* **1 € = 100 points** → `earn_rate_per_euro = 100.00`
* **Valeur d’1 point = 0,01 €** → `redeem_rate_euro_per_point = 0.0100`

## Public

> Aucun endpoint public.

---

## CLIENT (utilisateur authentifié)

### 1) Adhérer au programme (+200 points de bienvenue)

**POST** `/api/fidelite/join/`
**Acteurs** : tout utilisateur authentifié
**Body** : —
**Réponse 200** (si nouvelle adhésion → bonus appliqué) :

```json
{ "message": "Adhésion confirmée", "points_balance": 200 }
```

* Si l’utilisateur est déjà membre, aucune recréditation, on renvoie juste le solde courant.

### 2) Consulter mon solde et les taux

**GET** `/api/fidelite/points/`
**Réponse 200** :

```json
{
  "points_balance": 1250,
  "earn_rate_per_euro": "100.00",
  "redeem_rate_euro_per_point": "0.0100"
}
```

### 3) Lister mon historique

**GET** `/api/fidelite/transactions/`
**Réponse 200** :

```json
[
  { "id": 45, "kind": "EARN", "points": 500, "reason": "Order #1021", "related_order_id": 1021, "created_at": "..." },
  { "id": 46, "kind": "SPEND", "points": -200, "reason": "Spend (manual)", "related_order_id": null, "created_at": "..." }
]
```

### 4) Dépenser des points (manuel)

**POST** `/api/fidelite/use/`
**Body** :

```json
{ "points": 200 }
```

**Réponses** :

* `200` :

  ```json
  { "message":"Points dépensés", "points_spent":200, "euro_value":"2.00", "points_balance":1050 }
  ```
* `400` : nombre invalide / solde insuffisant

> Note : en pratique, préférez déduire des points **au paiement** (checkout) dans le module `orders`.

