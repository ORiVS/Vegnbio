from decimal import Decimal
from django.db import transaction
from rest_framework import permissions, status, views
from rest_framework.response import Response

from .models import LoyaltyProgram, Membership, PointsTransaction

def get_program():
    program, _ = LoyaltyProgram.objects.get_or_create(id=1)
    return program

def get_or_create_membership(user):
    membership, _ = Membership.objects.get_or_create(user=user)
    return membership

class JoinProgramView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        membership = get_or_create_membership(request.user)
        return Response({"message": "Adhésion confirmée", "points_balance": membership.points_balance})


class PointsBalanceView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        membership = get_or_create_membership(request.user)
        program = get_program()
        return Response({
            "points_balance": membership.points_balance,
            "earn_rate_per_euro": str(program.earn_rate_per_euro),
            "redeem_rate_euro_per_point": str(program.redeem_rate_euro_per_point),
        })


class TransactionsListView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        membership = get_or_create_membership(request.user)
        qs = membership.transactions.all()
        from .serializers import PointsTransactionSerializer
        return Response(PointsTransactionSerializer(qs, many=True).data)


class SpendPointsView(views.APIView):
    """
    Dépense des points sans commande (ajustement manuel côté client).
    Pour l'application pratique, on préfère l'usage de points au checkout (module orders).
    """
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        points = int(request.data.get("points", 0))
        if points <= 0:
            return Response({"detail": "Nombre de points invalide."}, status=status.HTTP_400_BAD_REQUEST)

        membership = get_or_create_membership(request.user)
        if membership.points_balance < points:
            return Response({"detail": "Solde de points insuffisant."}, status=status.HTTP_400_BAD_REQUEST)

        membership.points_balance -= points
        membership.save()
        PointsTransaction.objects.create(
            membership=membership,
            kind=PointsTransaction.SPEND,
            points=-points,
            reason="Spend (manual)",
        )
        program = get_program()
        euro_value = Decimal(points) * program.redeem_rate_euro_per_point
        return Response({"message": "Points dépensés", "points_spent": points, "euro_value": str(euro_value), "points_balance": membership.points_balance})
