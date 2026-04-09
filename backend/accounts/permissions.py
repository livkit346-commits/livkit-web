from rest_framework.permissions import BasePermission

class IsAuthenticatedAndNotBanned(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return user.is_authenticated and not user.is_banned


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        token = request.auth
        user = request.user

        if not user.is_authenticated or not token:
            return False

        if token.get("token_type") != "admin":
            return False

        if token.get("token_version") != user.token_version:
            return False

        return user.role in ["ADMIN_LIMITED", "ADMIN_MAIN"]



class IsMainAdmin(BasePermission):
    def has_permission(self, request, view):
        token = request.auth

        return (
            request.user.is_authenticated and
            token is not None and
            token.get("token_type") == "admin" and
            request.user.role == "ADMIN_MAIN"
        )


class HasLifetimeAccess(BasePermission):
    def has_permission(self, request, view):
        user = request.user

        if user.role.startswith('ADMIN'):
            return True

        return user.has_lifetime_access
