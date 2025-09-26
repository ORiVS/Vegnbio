Parfait—voici la **documentation narrative par rôle** pour l’app **Menu** (allergènes, produits, plats, disponibilités, menus). Je colle à ton code (viewsets, permissions) et je montre les bodies + exemples rapides.

---

# Vue d’ensemble

* **Base path** : `/api/menu/`
* **Règle d’accès** :

  * **Public (sans token)** : lecture (GET) autorisée sur **toutes** les ressources.
  * **RESTAURATEUR** (auth) : création / modification / suppression, + actions `publish/unpublish` des menus, `activate/deactivate` des plats.
* **Domaines** :

  * `Allergen` (référentiel)
  * `Product` (ingrédients)
  * `Dish` (plats)
  * `DishAvailability` (disponibilités par restaurant et date)
  * `Menu` + `MenuItem` (menus, publications)

> NB : Les décimaux (`price`) peuvent être envoyés en nombre (ex. `12.90`) ou string (`"12.90"`) selon l’outil client. Ton serializer accepte des `DecimalField`.

---

# Rôle : Public (lecture sans authentification)

## Allergènes

### Lister

**GET** `/allergens/`

### Détail

**GET** `/allergens/{id}/`

---

## Produits

### Lister (+ filtres)

**GET** `/products/?is_bio=true|false&region=Île-de-France&allergen=GLUTEN,SESAME`

### Détail

**GET** `/products/{id}/`

---

## Plats

### Lister (+ filtres)

**GET** `/dishes/?is_active=true|false&is_vegan=true|false&exclude_allergens=GLUTEN,LAIT`

Chaque plat inclut `allergens` (union des allergènes des produits + `extra_allergens`).

### Détail

**GET** `/dishes/{id}/`

---

## Disponibilités (par restaurant / date)

### Lister

**GET** `/dish-availability/?restaurant=12&date=2025-10-01`

### Détail

**GET** `/dish-availability/{id}/`

---

## Menus (seulement publiés par défaut)

### Lister (+ filtres)

**GET** `/menus/?restaurant=12&date=2025-10-15`

> ⚠️ Par défaut, seuls les menus `is_published=true` sont renvoyés.
> Pour inclure les non-publiés (nécessite auth RESTAURATEUR mais la route est la même) : `?include_unpublished=true`.

### Détail

**GET** `/menus/{id}/`

---

# Rôle : RESTAURATEUR (CRUD + actions)

> Auth : `Authorization: Bearer <access_token>` + rôle `RESTAURATEUR`.

## Allergènes (CRUD)

### Créer

**POST** `/allergens/`

```json
{ "code": "SESAME", "label": "Sésame" }
```

### Mettre à jour

**PUT/PATCH** `/allergens/{id}/`

```json
{ "label": "Graines de sésame" }
```

### Supprimer

**DELETE** `/allergens/{id}/`

---

## Produits (CRUD + filtres)

### Créer

**POST** `/products/`

```json
{
  "name": "Farine T80",
  "is_bio": true,
  "producer_name": "Moulin de la Plaine",
  "region": "Île-de-France",
  "is_vegetarian": true,
  "allergens": [1, 3]   // IDs d'allergènes (optionnel)
}
```

### Mettre à jour

**PUT/PATCH** `/products/{id}/` (mêmes champs)

### Supprimer

**DELETE** `/products/{id}/`

---

## Plats (CRUD + activation)

### Créer

**POST** `/dishes/`

```json
{
  "name": "Risotto aux cèpes",
  "description": "Crémeux, parmesan AOP",
  "price": 14.90,
  "is_vegan": false,
  "is_active": true,
  "products": [5, 9],          // IDs Product (optionnel)
  "extra_allergens": [2, 7]    // IDs Allergen (optionnel)
}
```

**Règle** : tous les `products` liés doivent être **végétariens** (`is_vegetarian=true`), sinon 400.

### Mettre à jour

**PUT/PATCH** `/dishes/{id}/`

### (Dés)activer un plat

**PATCH** `/dishes/{id}/deactivate/` → `{ "status": "dish deactivated" }`
**PATCH** `/dishes/{id}/activate/` → `{ "status": "dish activated" }`

### Supprimer

**DELETE** `/dishes/{id}/`

---

## Disponibilités (CRUD)

### Créer

**POST** `/dish-availability/`

```json
{
  "dish": 42,
  "restaurant": 12,
  "date": "2025-10-01",
  "is_available": false
}
```

**Contrainte** : `(dish, restaurant, date)` **unique**.

### Mettre à jour

**PUT/PATCH** `/dish-availability/{id}/`

### Supprimer

**DELETE** `/dish-availability/{id}/`

---

## Menus (CRUD + publication)

### Créer un menu (avec items)

**POST** `/menus/`

```json
{
  "title": "Menu Automne",
  "description": "Sélection de saison",
  "start_date": "2025-10-01",
  "end_date": "2025-12-15",
  "restaurants": [12, 13],      // Multi-restos
  "is_published": false,         // publication via action dédiée
  "items": [
    { "dish_id": 21, "course_type": "ENTREE" },
    { "dish_id": 42, "course_type": "PLAT" },
    { "dish_id": 77, "course_type": "DESSERT" }
  ]
}
```

**Règles** :

* `end_date >= start_date`.
* `course_type ∈ {ENTREE, PLAT, DESSERT, BOISSON}`.
* `(menu, dish, course_type)` **unique**.
* Les `restaurants` sont une **liste d’IDs** (ManyToMany).

### Mettre à jour un menu (remplacement complet des items si fournis)

**PUT/PATCH** `/menus/{id}/`

```json
{
  "title": "Menu Automne (v2)",
  "restaurants": [12],           // remplace le set
  "items": [
    { "dish_id": 42, "course_type": "PLAT" },
    { "dish_id": 77, "course_type": "DESSERT" }
  ]
}
```

> Si `items` est présent, le code **supprime** tous les items existants, puis recrée à partir de la liste.

### Publier / Dépublier

**POST** `/menus/{id}/publish/`

* Refus si le menu n’a **aucun item** (400).
* Réponse : `{ "status": "menu published" }`.

**POST** `/menus/{id}/unpublish/`

* Réponse : `{ "status": "menu unpublished" }`.

### Supprimer

**DELETE** `/menus/{id}/`

---