from rest_framework.permissions import BasePermission


class CanManageTickets(BasePermission):
    message = "This action is restricted to the Tech Team and TLs."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.can_manage_tickets
        )

