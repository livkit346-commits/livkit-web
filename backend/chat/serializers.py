from rest_framework import serializers
from .models import Conversation, ConversationMember, Message
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


# --------------------------------------------------
# USER MINI (UNCHANGED)
# --------------------------------------------------

class UserMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username")


# --------------------------------------------------
# MESSAGE SERIALIZER (WHATSAPP-READY)
# --------------------------------------------------

class MessageSerializer(serializers.ModelSerializer):
    sender = UserMiniSerializer(read_only=True)

    # 👇 Flutter helpers
    sender_id = serializers.IntegerField(source="sender.id", read_only=True)
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = (
            "id",
            "conversation",      # keep for backward compatibility
            "sender",
            "sender_id",
            "is_mine",
            "type",
            "content",
            "created_at",
            "edited_at",
            "is_deleted",
        )
        read_only_fields = (
            "id",
            "sender",
            "created_at",
            "sender_id",
            "is_mine",
        )

    def get_is_mine(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.sender_id == request.user.id
        return False


# --------------------------------------------------
# CONVERSATION SERIALIZER (CHAT LIST FIX)
# --------------------------------------------------

class ConversationSerializer(serializers.ModelSerializer):
    members = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = (
            "id",
            "type",
            "title",
            "created_at",
            "last_message_at",
            "members",
            "last_message",
        )

    def get_members(self, obj):
        members = obj.members.select_related("user")
        return UserMiniSerializer(
            [m.user for m in members],
            many=True
        ).data

    def get_last_message(self, obj):
        # ✅ ignore deleted or expired messages
        msg = (
            obj.messages
            .filter(
                is_deleted=False,
                expires_at__gt=timezone.now()
            )
            .order_by("-created_at")
            .first()
        )

        if not msg:
            return None

        return MessageSerializer(
            msg,
            context=self.context
        ).data
