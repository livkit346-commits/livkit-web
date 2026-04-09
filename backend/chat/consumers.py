import json
import re
from uuid import UUID

from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone

from .models import (
    Conversation,
    ConversationMember,
    Message,
    MessageReceipt,
)


def safe_group_name(conversation_id: str) -> str:
    """
    Sanitize conversation_id to a valid Channels group name.
    """
    return re.sub(r'[^a-zA-Z0-9_\-\.]', '_', conversation_id)[:100]


class ChatConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.group_name = None
        self.conversation_id = None
        self.conversation = None

    # -------------------- CONNECT --------------------

    async def connect(self):
        user = self.scope.get("user")
        conversation_id = self.scope["url_route"]["kwargs"].get("conversation_id")

        # Basic auth & param checks
        if not user or not user.is_authenticated or not conversation_id:
            await self.close()
            return

        # Validate UUID
        try:
            conversation_uuid = UUID(conversation_id)
        except Exception:
            print("Invalid conversation_id:", conversation_id)
            await self.close()
            return

        # Fetch conversation
        conversation = await Conversation.objects.filter(
            id=conversation_uuid
        ).afirst()

        if not conversation:
            print("Conversation not found:", conversation_id)
            await self.close()
            return

        # ✅ MEMBERSHIP RULES
        # GLOBAL → implicit membership
        # NON-GLOBAL → must exist in ConversationMember
        if conversation.type != Conversation.Type.GLOBAL:
            is_member = await ConversationMember.objects.filter(
                conversation=conversation,
                user=user,
                is_banned=False,
            ).aexists()

            if not is_member:
                print(f"User {user.email} is not a member of {conversation_id}")
                await self.close()
                return

        # Passed all checks
        self.conversation_id = conversation_uuid
        self.conversation = conversation
        self.group_name = f"chat_{safe_group_name(conversation_id)}"

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name,
        )

        await self.accept()
        print(f"WS CONNECT: user={user.email} conversation={conversation_id}")

    # -------------------- DISCONNECT --------------------

    async def disconnect(self, close_code):
        if self.group_name:
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name,
            )

    # -------------------- RECEIVE --------------------

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        event_type = data.get("type")
        payload = data.get("payload", {})
        user = self.scope.get("user")

        if not user or not user.is_authenticated:
            return

        # -------- MESSAGE SEND --------
        if event_type == "message.send":
            content = payload.get("content")
            message_type = payload.get("message_type", "TEXT")

            if not content:
                return

            # ✅ Persist message (WhatsApp-style)
            message = await Message.objects.acreate(
                conversation=self.conversation,
                sender=user,
                type=message_type,
                content={"text": content},
                created_at=timezone.now(),
            )

            # ❗ last_message_at is now handled in Message.save()
            # ❗ No duplicate update here

            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "message_new",
                    "message": {
                        "id": str(message.id),
                        "sender": user.username,
                        "type": message.type,
                        "content": message.content,
                        "created_at": message.created_at.isoformat(),
                    },
                },
            )

        # -------- TYPING --------
        elif event_type in ("typing.start", "typing.stop"):
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "typing_event",
                    "user": user.username,
                    "is_typing": event_type == "typing.start",
                },
            )

        # -------- READ RECEIPT --------
        elif event_type == "message.read":
            message_id = payload.get("message_id")
            if not message_id:
                return

            # ✅ Correct WhatsApp-style read receipt
            await MessageReceipt.objects.aupdate_or_create(
                message_id=message_id,
                user=user,
                defaults={"status": MessageReceipt.Status.READ},
            )

            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "message_read",
                    "message_id": message_id,
                    "user": user.username,
                },
            )

    # -------------------- GROUP EVENTS --------------------

    async def message_new(self, event):
        await self.send(text_data=json.dumps({
            "type": "message.new",
            **event,
        }))

    async def typing_event(self, event):
        await self.send(text_data=json.dumps({
            "type": "typing",
            "user": event["user"],
            "is_typing": event["is_typing"],
        }))

    async def message_read(self, event):
        await self.send(text_data=json.dumps({
            "type": "message.read",
            "message_id": event["message_id"],
            "user": event["user"],
        }))
