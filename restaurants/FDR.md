parfait — je reprends **l’app restaurants** et je fais la **documentation narrative groupée par rôle**.
On garde les mêmes endpoints, mais triés par **Public**, **CLIENT**, **RESTAURATEUR (owner)** et **ADMIN**.
Base path : `/api/restaurants/` — Auth : `Authorization: Bearer <access_token>` (sauf endpoints publics).

---

# Public (sans authentification)

## Consulter les restaurants

**GET** `/restaurants/`
**GET** `/restaurants/{id}/`
Body : —
But : découvrir l’offre et voir les salles (en lecture seule).

## Consulter les évènements d’un restaurant

**GET** `/restaurants/{id}/evenements/`
Body : —
But : calendrier public d’un restaurant.

## Parcourir les évènements (catalogue)

**GET** `/evenements/`
Query (optionnels) : `restaurant`, `date`, `type`, `status`, `is_public=true|false`
Body : —
Note : si non authentifié, ne renvoie que `status=PUBLISHED` et `is_public=true`.

---

# CLIENT

> Un **CLIENT** gère uniquement **ses propres réservations**.

## Créer une réservation

**POST** `/reservations/`
Body :

```json
{
  "restaurant": 12,
  "date": "2025-10-15",
  "start_time": "19:30:00",
  "end_time": "21:30:00",
  "party_size": 6
}
```

Règles :

* pas dans le passé, `start_time < end_time`, horaires d’ouverture respectés ;
* pas d’évènement **bloquant** chevauchant ;
* pas de réservation “**full_restaurant**” existante sur le créneau.

## Voir mes réservations

**GET** `/reservations/` (filtré par le backend)
**GET** `/reservations/my_reservations/`
Body : —

## Voir le détail d’une de mes réservations

**GET** `/reservations/{id}/`
Body : —

## Modifier une de mes réservations (si PENDING)

**PUT/PATCH** `/reservations/{id}/`
Body : mêmes champs que création
Note : refusé si `status != PENDING`.

## Annuler une de mes réservations (si PENDING)

**DELETE** `/reservations/{id}/`
ou **POST** `/reservations/{id}/cancel/`
Body : —

---

# RESTAURATEUR 

> Un **RESTAURATEUR** agit **sur ses restaurants** et toutes les entités rattachées (rooms, réservations, évènements, fermetures).

## Gérer mes restaurants

* **GET** `/restaurants/{id}/` (public), **mais** la mise à jour est protégée.
* **PUT/PATCH** `/restaurants/{id}/` (owner ou ADMIN)
  Body (ex) :

```json
{
  "name": "Veg'N Bio Paris 11",
  "capacity": 120,
  "animations_enabled": true,
  "animation_day": "Mardi",
  "opening_time_mon_to_thu": "09:00:00",
  "closing_time_mon_to_thu": "23:59:00"
}
```

## Gérer les salles (rooms)

* **GET** `/rooms/`, `/rooms/{id}/` (lecture publique)
* **POST** `/rooms/` (owner) :

```json
{ "restaurant": 12, "name": "Salle Jardin", "capacity": 40 }
```

* **PUT/PATCH** `/rooms/{id}/` (owner) — la room doit rester dans un restaurant possédé
* **DELETE** `/rooms/{id}/` (owner)

## Créer une réservation au nom d’un client (dans MES restaurants)

**POST** `/reservations/`
Body :

```json
{
  "restaurant": 12,
  "date": "2025-10-15",
  "start_time": "19:30:00",
  "end_time": "21:30:00",
  "party_size": 6,
  "customer_email": "client@example.com"
}
```

Notes :

* `customer_email` est **requis** quand c’est le restaurateur qui crée ;
* le restaurant doit être **à moi**.

## Voir et filtrer les réservations de mes restaurants

**GET** `/reservations/` (le backend filtre automatiquement sur `restaurant__owner=request.user`)
**GET** `/restaurants/{restaurant_id}/reservations/?status=PENDING|CONFIRMED|CANCELLED`

## Assigner/Confirmer une réservation

**POST** `/reservations/{id}/assign/`
Deux scénarios :

A) **Tout le restaurant** :

```json
{ "full_restaurant": true }
```

→ Refus si salles déjà réservées ou un autre “full_restaurant” sur le créneau.

B) **Salle précise** :

```json
{ "room": 34 }
```

→ Vérifie capacité (≥ `party_size`) + conflits salle/full.

Effet : `status = CONFIRMED` si OK.

## Modérer une réservation

**POST** `/reservations/{id}/moderate/`
Body :

```json
{ "status": "CANCELLED" }   // ou "CONFIRMED"
```

(pratique pour confirmations manuelles ou annulations).

## Annuler une réservation (PENDING)

**DELETE** `/reservations/{id}/`
ou **POST** `/reservations/{id}/cancel/`

RESTAURATEUR : Évènements avec confirmation producteur et deadline
Créer un évènement avec confirmation producteur

POST /evenements/
Acteurs : RESTAURATEUR (owner) ou ADMIN
Body (JSON) :

{
  "restaurant": 12,
  "title": "Soirée producteurs",
  "description": "Dégustation bio",
  "type": "ANIMATION",
  "date": "2025-11-05",
  "start_time": "18:00:00",
  "end_time": "21:00:00",
  "capacity": 80,
  "is_public": true,
  "is_blocking": true,

  "requires_supplier_confirmation": true,
  "supplier_deadline_days": 14
}


Ce que ça implique :

requires_supplier_confirmation=true indique que les invités de type producteur doivent accepter l’invitation avant une date limite.

supplier_deadline_days définit cette limite à J – N jours par rapport à la date de l’évènement.

La méthode supplier_deadline_at() (déjà dans le modèle) calcule l’échéance : 23:59:59 du jour (date – N jours).

Inviter des producteurs avec une deadline visible dans l’e-mail

POST /evenements/{id}/invite/
Acteurs : RESTAURATEUR (owner) ou ADMIN
Body (JSON) :

{
  "email": "ferme@exemple.com",
  "phone": null
  /* si tu as ajouté le champ (recommandé) :
  "invitee_role": "SUPPLIER"
  */
}


Comportement e-mail :

La fonction send_invite_email() ajoute une ligne “date limite d’acceptation” à l’e-mail si l’invitation est destinée à un producteur et que requires_supplier_confirmation est true.

La date affichée vient de event.supplier_deadline_at().

ℹ️ Si tu n’as pas encore ajouté un champ pour distinguer le rôle de l’invité (ex. invitee_role=SUPPLIER|GUEST sur EventInvite), l’e-mail ne pourra pas savoir qu’il s’agit d’un producteur. Ajoute ce champ pour activer l’affichage conditionnel (comme on l’a proposé).

Inviter en masse des producteurs

POST /evenements/{id}/invite_bulk/
Acteurs : RESTAURATEUR (owner) ou ADMIN
Body (JSON) :

{
  "emails": ["ferme1@ex.com", "ferme2@ex.com"]
  /* si tu as étendu l’endpoint :
  "invitee_role": "SUPPLIER"
  */
}


Chaque invitation générée reçoit un e-mail avec la deadline si requires_supplier_confirmation=true et invitee_role="SUPPLIER".

Accepter l’invitation (avec contrôle de deadline)

POST /evenements/{id}/accept_invite/
Acteurs : authentifié (destinataire)
Body (JSON) :

{ "token": "<token-reçu-par-email>" }


Règle fonctionnelle cible :

Si requires_supplier_confirmation=true et l’invitation est pour un producteur, l’acceptation doit se faire avant supplier_deadline_at().

Après l’échéance, l’API doit refuser avec un message du style :
“Date limite d’acceptation dépassée pour les producteurs.”


RESTAURATEUR :

Définit requires_supplier_confirmation + supplier_deadline_days à la création de l’évènement.

Envoie des invitations producteurs → l’e-mail affiche la deadline.

Producteur invité :

Doit cliquer/valider l’invitation avant la date limite (sinon refus côté API si le contrôle est activé).

ADMIN :

Peut corriger/désactiver la contrainte si besoin (en modifiant l’évènement).

## Dashboard de disponibilité (vision jour)

**GET** `/restaurants/{restaurant_id}/dashboard/?date=YYYY-MM-DD`
Réponse : rooms + créneaux + évènements ce jour.

## Événements (sur MES restaurants)

* **POST** `/evenements/` :

```json
{
  "restaurant": 12,
  "title": "Soirée producteurs",
  "description": "Dégustation bio",
  "type": "ANIMATION",
  "date": "2025-11-05",
  "start_time": "18:00:00",
  "end_time": "21:00:00",
  "capacity": 80,
  "is_public": true,
  "is_blocking": true
}
```

Validations : pas dans le passé, `start<end`, horaires d’ouverture, pas de chevauchement avec **évènement bloquant**.

* **PUT/PATCH/DELETE** `/evenements/{id}/` (owner)
* **POST** `/evenements/{id}/publish/` → `status=PUBLISHED`, `published_at=now`
* **POST** `/evenements/{id}/cancel/` → `status=CANCELLED`, notifie les inscrits
* **POST** `/evenements/{id}/close/` → `status=FULL`
* **POST** `/evenements/{id}/reopen/` → `status=PUBLISHED`

### Invitations & inscriptions

* **POST** `/evenements/{id}/invite/` :

```json
{ "email": "invite@exemple.com", "phone": null }
```

→ crée une invitation (token auto, expiration 14 jours) + email de lien.

* **POST** `/evenements/{id}/invite_bulk/` :

```json
{ "emails": ["a@ex.com","b@ex.com"] }
```

* **GET** `/evenements/{id}/registrations/`

  * owner/ADMIN : liste complète `{ registrations: [...] }`
  * autres : `{ count, me: { registered, registered_at } }`

* **POST** `/evenements/{id}/accept_invite/` :

```json
{ "token": "<token-reçu-par-email>" }
```

→ crée une inscription si places dispo (sinon `FULL`).

## Fermetures (closures) — MES restaurants

* **GET** `/closures/` (retourne mes restos ; ADMIN voit tout)
* **POST** `/closures/` :

```json
{ "restaurant": 12, "date": "2025-12-25", "reason": "Noël" }
```

* **GET/PUT/PATCH/DELETE** `/closures/{id}/`

## Vues agrégées (mon périmètre)

* **GET** `/reservations/all/` (je vois mes restos)
* **GET** `/reservations/statistics/` (stats par resto/salle)

---

# ADMIN

> **ADMIN** peut administrer l’ensemble du périmètre.

## Gérer les restaurants (CRUD complet)

* **POST** `/restaurants/` (création)
* **PUT/PATCH** `/restaurants/{id}/` (également owner autorisé)
* **DELETE** `/restaurants/{id}/`

## Lecture globale

* **GET** `/reservations/` (toutes)
* **GET** `/reservations/all/` ; **GET** `/reservations/statistics/`
* **GET** `/closures/` (toutes)

## Modération/override

* Peut mettre à jour des **rooms**/**évènements**/**réservations** comme un owner (les vues vérifient owner **ou** ADMIN).
* Peut utiliser toutes les actions d’évènements : `publish/cancel/close/reopen/invite/invite_bulk/accept_invite/registrations`.

---

## Sécurité & validations — points clés par rôle

* **CLIENT** : sandboxé à **ses** réservations ; modification/annulation uniquement en `PENDING`.
* **RESTAURATEUR** : limité à **ses** restaurants ; assignation **ou** full-restaurant exclusive ; évènements soumis aux horaires et aux conflits bloquants.
* **ADMIN** : superpouvoirs ; idéal pour bootstrap (création de restaurants) et support.

---

## Exemples rapides (cURL)

### CLIENT — créer une réservation

```bash
curl -X POST https://vegnbio.onrender.com/api/restaurants/reservations/ \
 -H "Authorization: Bearer <ACCESS>" -H "Content-Type: application/json" \
 -d '{ "restaurant":12, "date":"2025-10-15", "start_time":"19:30:00",
       "end_time":"21:30:00", "party_size":6 }'
```

### RESTAURATEUR — affecter une salle

```bash
curl -X POST https://vegnbio.onrender.com/api/restaurants/reservations/57/assign/ \
 -H "Authorization: Bearer <ACCESS>" -H "Content-Type: application/json" \
 -d '{ "room": 34 }'
```

### RESTAURATEUR — réserver tout le restaurant

```bash
curl -X POST https://vegnbio.onrender.com/api/restaurants/reservations/57/assign/ \
 -H "Authorization: Bearer <ACCESS>" -H "Content-Type: application/json" \
 -d '{ "full_restaurant": true }'
```

### ADMIN — créer un restaurant

```bash
curl -X POST https://vegnbio.onrender.com/api/restaurants/restaurants/ \
 -H "Authorization: Bearer <ACCESS>" -H "Content-Type: application/json" \
 -d '{ "name":"VegNBio 11e", "address":"25 Rue ...", "city":"Paris",
       "postal_code":"75011", "capacity":120 }'
```
