from rest_framework.permissions import BasePermission


class IsAdminRole(BasePermission):
    """Allows access only to authenticated users with the admin role."""

    message = 'Admin access required.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, 'is_admin', False))
