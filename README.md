Veg’N Bio — Documentation de ce qui a été fait
0) Périmètre & stack

Backend : Django + DRF, JWT (login/register), modèles métiers (menu, POS, évènements, réservations).

Frontend : React + Redux, Axios.

Multi-sites : restaurants #1..#7, propriétaires (role=RESTAURATEUR).

1) Comptes & rôles (accounts)

Modèles

CustomUser(role ∈ {CLIENT, FOURNISSEUR, RESTAURATEUR, ADMIN})

UserProfile (téléphone, adresse, allergies / company_name, etc.)

Endpoints

POST /api/accounts/register/ (serializer: RegisterSerializer)

POST /api/accounts/login/ → JWT

GET /api/accounts/me/ (profil + restaurants de l’owner)

PATCH /api/accounts/me/update/ (nom + profil)

Règles

Email unique + validé.

Création d’un profil à l’inscription.

Si role=RESTAURATEUR + restaurant_id, association comme owner.

Seed : seeds/users.seed.json + collection Postman data-driven (déjà fournie/exécutée).

2) Module Menu (allergènes, produits, plats, disponibilités, menus)
2.1 Modèles & validations

Allergen(code,label) — référentiel.

Product(name, is_bio, region, is_vegetarian, allergens M2M)

Dish(name, price, is_vegan, is_active, products M2M, extra_allergens M2M)

Validation : aucun produit non-végétarien autorisé.

allergens_union_qs() = union (products.allergens ∪ extra_allergens).

DishAvailability(dish, restaurant, date, is_available) unique par (plat, resto, date).

Menu(title, dates, restaurants M2M, is_published)

MenuItem(menu, dish, course_type ∈ {ENTREE, PLAT, DESSERT, BOISSON}).

2.2 Endpoints (public lecture, écriture restaurateur)

GET/POST /api/menu/allergens/

GET/POST /api/menu/products/ + filtres ?is_bio&region&allergen=CODE1,CODE2

GET/POST /api/menu/dishes/ + filtres ?is_active&is_vegan&exclude_allergens=…

Actions: PATCH /dishes/{id}/activate|deactivate/

GET/POST /api/menu/dish-availability/ + filtres ?restaurant=ID&date=YYYY-MM-DD

GET/POST /api/menu/menus/

Filtrage par défaut: seulement is_published=true

Filtres: ?restaurant=ID&date=YYYY-MM-DD (inclusion si start_date≤date≤end_date)

Actions: POST /menus/{id}/publish|unpublish/

2.3 Données & seed

Plats : 10 plats (IDs 1..10) + allergènes calculés.

Disponibilités : générées aléatoirement du jour → 20 octobre pour restaurants #1..#7 (JSON déjà fourni), avec ruptures ponctuelles.

Menus : S38→S47 pour #1..#4 et séries distinctes pour #5..#7 (dates exactes, items par type de course, is_published=true).

2.4 Ce que ça garantit côté UI

Un plat n’est cliquable dans un menu que s’il est disponible pour le restaurant + la date du jour.

3) POS (caisse) : commandes, lignes, paiements, ticket
3.1 Modèles

Order(restaurant, status ∈ {OPEN,HOLD,PAID,CANCELLED,REFUNDED}, TVA, remises, totaux, paid_amount, change_due)

recalc_totals() : subtotal → discount → net → tax_total → total_due (arrondi 2 déc.)

ensure_mutable() : modifiable si OPEN|HOLD.

close_if_paid() : passe à PAID si paid_amount ≥ total_due.

OrderItem(order, dish?, custom_name?, unit_price, quantity≥1)

Payment(order, method ∈ {CASH,CARD,ONLINE}, amount)

3.2 Endpoints

GET/POST /api/pos/orders/ (+ filtres ?restaurant&date=YYYY-MM-DD)

Actions (sur /api/pos/orders/{id}/…):

Lignes :
POST add_item/ { dish, unit_price, quantity }
PATCH items/{itemId}/update/
DELETE items/{itemId}/remove/

Remise : POST apply_discount/ { discount_amount, discount_percent[0..100] }

Statut : POST hold/, POST reopen/, POST cancel/

Encaissement : POST checkout/ { method, amount }
→ crée Payment + recalc + close si payé

Ticket (JSON) : GET ticket/ (composition sûre, items actifs, totaux)

Résumé : GET summary/?restaurant&date → { count, turnover }

3.3 Ticket PDF

Endpoint : GET /api/pos/orders/{id}/receipt.pdf
(présenté avec un template HTML/CSS imprimable : logo/nom resto, n° ticket, date/heure, lignes, HT/TVA/TTC, remises, mode de paiement, montant reçu & rendu, pied de page).

Option debug : GET /api/pos/orders/{id}/receipt.html (même rendu côté navigateur).

✱ Le front ouvre la version PDF dans un nouvel onglet depuis la page Commandes.

4) Évènements, salles, réservations, fermetures
4.1 Modèles

Restaurant : coordonnées, horaires détaillés (lun-jeu, ven, sam, dim), gestion des nocturnes (fermeture après minuit gérée), flags d’équipement.

is_time_range_within_opening(date, start, end) : valide un créneau selon le jour + spill overnight.

Room(restaurant, name, capacity) (unique par restaurant)

Reservation(customer|owner via email, room|full_restaurant, date, start_time, end_time, status)

Validations :

pas dans le passé / horaire cohérent

dans les horaires du restaurant

conflits : restaurant entier vs salles, et évènement bloquant sur le créneau

Evenement(restaurant, title, type, date, start/end, capacity?, is_public, is_blocking, status ∈ {DRAFT,PUBLISHED,FULL,CANCELLED}, room?, rrule?, created_by)

Timestamps : published_at, full_at, cancelled_at.

Validations : pas dans le passé, horaires d’ouverture, pas de chevauchement entre évènements bloquants (même salle ou global).

EvenementRegistration(event,user) (unique)

EventInvite(event, email/phone, token, expires_at) + acceptation.

RestaurantClosure(restaurant, date, reason) (fermeture exceptionnelle).

4.2 Endpoints

Restaurants

GET /api/restaurants/ (+ rooms inclus en lecture)

PATCH /api/restaurants/{id}/ (owner ou admin)

GET /api/restaurants/{id}/evenements/

Rooms

CRUD (écriture réservée owner du restaurant).

Reservations

CRUD avec validations ci-dessus

GET my_reservations/ (client)

POST {id}/moderate/ (owner → CONFIRMED|CANCELLED)

POST {id}/cancel/ (client/owner)

Dash :

GET /api/restaurants/{id}/reservations/ (owner)

GET /api/restaurants/{id}/availability_dashboard/?date=YYYY-MM-DD

GET /api/restaurants/reservations_stats/ (owner/admin)

Évènements

CRUD (écriture = owner/admin)

POST {id}/publish|cancel|close|reopen/

GET {id}/registrations/ (owner/admin → liste ; autres → résumé “me”)

POST {id}/invite/ (unitaire) / POST {id}/invite_bulk/ (e-mails)

4.3 Rôle des closures

Noter les fermetures exceptionnelles (jour férié, maintenance…).

Destinées à bloquer l’UI côté owner/ops (calendrier, planification), et à justifier l’indispo.

(Selon besoin, on peut étendre la validation pour empêcher réservations/évènements ces jours-là.)

5) Frontend livré (pages & logique)
5.1 Menu.jsx

Charge en parallèle : plats actifs, menus filtrés par ?restaurant&date, disponibilités du jour (/menu/dish-availability/).

Construit un availSet (IDs plats dispo aujourd’hui pour ce resto).

Dans l’affichage des menus :

Bouton désactivé si le plat n’est pas dispo → label “(Plat indisponible)”.

Clic plat → ensureOrder() (création OPEN) → addItem → ticket(orderId) pour sync.

5.2 CheckoutDialog.jsx

Normalize la réponse ticket() (robuste aux variations).

Espèces : saisie “montant donné”, calcule rendu & partiel ; sinon Carte encaisse le restant.

POST checkout/ → recalc & close ; callback succès.

5.3 Orders.jsx

Liste des commandes du restaurant (filtre Aujourd’hui/Toutes, tri par colonnes).

Actions : Hold / Reopen / Annuler / Encaisser.

Ticket : bouton qui ouvre le PDF (/api/pos/orders/{id}/receipt.pdf) dans un nouvel onglet.
(Fallback “voir JSON” possible via ticket()).

6) Permissions & sécurité

Lecture publique : menus publiés, évènements publiés & publics.

Écriture : owner sur ses restaurants (rooms, menus, disponibilités, évènements, POS) ; ADMIN partout.

Validations métier :

Plats 100 % végé (aucun product non-végétarien).

Menus: dates cohérentes, publication interdite si vide.

Réservations: horaires d’ouverture, conflits, évènement bloquant.

Évènements: pas dans le passé, horaires d’ouverture, pas de chevauchement bloquant.

POS: totaux recalculés à chaque modif, remises bornées, statut cohérent.

7) Tester rapidement (exemples)
7.1 Menus & disponibilités du jour

Menus filtrés jour+site :
GET /api/menu/menus/?restaurant=1&date=2025-09-17

Plats dispo du jour :
GET /api/menu/dish-availability/?restaurant=1&date=2025-09-17
→ renvoie les lignes disponibles (is_available=true) utilisées par l’UI.

7.2 POS

Créer commande : POST /api/pos/orders/ { "restaurant": 1, "note": "Sur place" }

Ajouter ligne : POST /api/pos/orders/{id}/add_item/ { "dish": 1, "unit_price": 11.90, "quantity": 1 }

Remise : POST /api/pos/orders/{id}/apply_discount/ { "discount_percent": 10 }

Encaisser (carte) : POST /api/pos/orders/{id}/checkout/ { "method":"CARD", "amount": <restant> }

Ticket PDF : GET /api/pos/orders/{id}/receipt.pdf

7.3 Évènements & réservations

Créer évènement bloquant (owner) → publish.

Essayer de réserver une salle sur le même créneau → erreur contrôlée.

Inviter par e-mail (invite / invite_bulk), accepter via accept_invite.

8) Seed & Postman

Users : seeds/users.seed.json + collection Postman (itérations par data file).

Menu : allergens, products, dishes (1..10), dish_availability (aléatoires jour→20/10 pour restos 1..7), menus S38→S47 (#1..#4 et #5..#7 distincts).

Évènements/Rooms/Reservations/Closures : 10 JSON chacun (couvrant jours & horaires d’ouverture, divers statuts/cas).

POS : jeu d’essai simple (création, ajout lignes, encaissement, ticket).

9) Points forts déjà livrés

Couplage fort menus ↔ disponibilités (zéro plat fantôme au clic).

Allergènes calculés automatiquement.

Horaires avancés (nocturnes) pour réservations/évènements.

Flux caisse complet : lignes, remises, paiements, ticket PDF.

Multi-sites & permissions owner/admin.

10) Prochaines itérations suggérées

QR code / lien public sur le ticket (consultation client).

Exports (journal Z, CSV mensuel).

Stats : CA, panier moyen, ventes par plat.

Intégration module “offres fournisseurs” pour composer les menus depuis l’offre (si activé).