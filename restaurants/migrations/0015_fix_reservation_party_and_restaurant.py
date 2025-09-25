# restaurants/migrations/0015_fix_reservation_party_and_restaurant.py
from django.db import migrations, models
import django.db.models.deletion


def fill_reservation_restaurant(apps, schema_editor):
    Reservation = apps.get_model("restaurants", "Reservation")
    Room = apps.get_model("restaurants", "Room")
    Restaurant = apps.get_model("restaurants", "Restaurant")

    # 1) tenter via la room
    for r in Reservation.objects.filter(restaurant__isnull=True, room__isnull=False):
        # si la salle a un restaurant, recopier
        try:
            r.restaurant_id = r.room.restaurant_id
            r.save(update_fields=["restaurant"])
        except Exception:
            pass

    # 2) fallback: si certains sont encore NULL, mettre sur le 1er restaurant existant
    first_restaurant = Restaurant.objects.order_by("id").first()
    if first_restaurant:
        Reservation.objects.filter(restaurant__isnull=True).update(restaurant_id=first_restaurant.id)


class Migration(migrations.Migration):

    dependencies = [
        ("restaurants", "0014_remove_eventinvite_restaurants_event_i_881b13_idx_and_more"),
    ]

    operations = [
        # IMPORTANT : 0014 a déjà ajouté party_size et a mis reservation.restaurant en null=True
        # Ici, on ne touche PAS à party_size et on ne tente PAS de le recréer.
        migrations.RunPython(fill_reservation_restaurant, migrations.RunPython.noop),

        # Puis on verrouille : restaurant devient NOT NULL
        migrations.AlterField(
            model_name="reservation",
            name="restaurant",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="reservations",
                to="restaurants.restaurant",
                null=False,
            ),
        ),
    ]
