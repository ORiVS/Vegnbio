from rest_framework.permissions import BasePermission

class IsSupplier(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and getattr(request.user, "role", None) == "FOURNISSEUR"

class IsRestaurateur(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and getattr(request.user, "role", None) == "RESTAURATEUR"

class IsAdminVegNBio(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and getattr(request.user, "role", None) == "ADMIN"
