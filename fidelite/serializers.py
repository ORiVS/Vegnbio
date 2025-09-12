from rest_framework import serializers
from .models import LoyaltyProgram, Membership, PointsTransaction

class LoyaltyProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoyaltyProgram
        fields = ["id", "name", "description", "earn_rate_per_euro", "redeem_rate_euro_per_point", "rules", "created_at"]


class MembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = ["user", "joined_at", "points_balance"]
        read_only_fields = ["user", "joined_at", "points_balance"]


class PointsTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PointsTransaction
        fields = ["id", "kind", "points", "reason", "related_order_id", "created_at"]
