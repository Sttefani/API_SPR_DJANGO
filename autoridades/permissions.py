from rest_framework.permissions import BasePermission, IsAuthenticated
from usuarios.permissions import IsSuperAdminUser


class AutoridadePermission(BasePermission):
    def has_permission(self, request, view):
        if request.method == "DELETE":
            return IsSuperAdminUser().has_permission(request, view)
        return IsAuthenticated().has_permission(request, view)
