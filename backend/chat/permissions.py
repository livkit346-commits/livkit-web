from rest_framework.permissions import BasePermission
from .models import ConversationMember


class IsConversationMember(BasePermission):
    def has_permission(self, request, view):
        conversation_id = view.kwargs.get("conversation_id") or view.kwargs.get("pk")
        if not conversation_id:
            return False

        return ConversationMember.objects.filter(
            conversation_id=conversation_id,
            user=request.user,
            is_banned=False,
        ).exists()
