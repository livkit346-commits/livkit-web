import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from datetime import timedelta

User = settings.AUTH_USER_MODEL


# -------------------------
# FRIEND REQUESTS
# -------------------------
class FriendRequest(models.Model):
    sender = models.ForeignKey(
        User,
        related_name="sent_requests",
        on_delete=models.CASCADE,
    )
    receiver = models.ForeignKey(
        User,
        related_name="received_requests",
        on_delete=models.CASCADE,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    # None = pending | True = accepted | False = rejected
    accepted = models.BooleanField(null=True)

    class Meta:
        unique_together = ("sender", "receiver")
        indexes = [
            models.Index(fields=["sender", "receiver"]),
        ]

    def __str__(self):
        return f"{self.sender} → {self.receiver} ({self.accepted})"


# -------------------------
# CONVERSATIONS
# -------------------------
class Conversation(models.Model):
    class Type(models.TextChoices):
        PRIVATE = "PRIVATE", "Private"
        GROUP = "GROUP", "Group"
        GLOBAL = "GLOBAL", "Global"
        LIVE = "LIVE", "Live Stream"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    type = models.CharField(
        max_length=10,
        choices=Type.choices,
        db_index=True,
    )

    title = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_conversations",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    # 🔹 WhatsApp-style ordering & chat list preview support
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["type"]),
            models.Index(fields=["last_message_at"]),
        ]

    def clean(self):
        """
        Enforce conversation invariants.
        """
        if self.type == self.Type.GLOBAL:
            if self.created_by is not None:
                raise ValidationError("Global conversation cannot have a creator.")
            if self.title is None:
                self.title = "Global Chat"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.type} | {self.id}"


# -------------------------
# CONVERSATION MEMBERS
# -------------------------
class ConversationMember(models.Model):
    class Role(models.TextChoices):
        OWNER = "OWNER", "Owner"
        ADMIN = "ADMIN", "Admin"
        MEMBER = "MEMBER", "Member"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="members",
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="chat_memberships",
    )

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.MEMBER,
    )

    joined_at = models.DateTimeField(auto_now_add=True)

    last_read_message = models.ForeignKey(
        "Message",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    is_muted = models.BooleanField(default=False)
    is_banned = models.BooleanField(default=False)

    class Meta:
        unique_together = ("conversation", "user")
        indexes = [
            models.Index(fields=["conversation", "user"]),
        ]

    def clean(self):
        """
        GLOBAL chat uses implicit membership.
        Only bans/mutes are allowed.
        """
        if self.conversation.type == Conversation.Type.GLOBAL:
            if self.role != self.Role.MEMBER:
                raise ValidationError("Global chat members cannot have roles.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user} in {self.conversation_id}"


# -------------------------
# MESSAGES
# -------------------------
class Message(models.Model):
    class Type(models.TextChoices):
        TEXT = "TEXT", "Text"
        IMAGE = "IMAGE", "Image"
        SYSTEM = "SYSTEM", "System"
        GIFT = "GIFT", "Gift"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )

    sender = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_messages",
    )

    type = models.CharField(
        max_length=10,
        choices=Type.choices,
        db_index=True,
    )

    content = models.JSONField()

    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)

    # 🔹 Soft delete (WhatsApp-like)
    is_deleted = models.BooleanField(default=False)

    # 🔹 Retention support (2–3 months rolling cleanup)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
        ]

    def save(self, *args, **kwargs):
        is_new = self._state.adding

        # 🔹 Auto-set expiration (90 days)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=90)

        super().save(*args, **kwargs)

        # 🔹 Update conversation ordering ONLY on new message
        if is_new:
            Conversation.objects.filter(
                id=self.conversation_id
            ).update(last_message_at=self.created_at)

    def __str__(self):
        return f"Message {self.id}"


# -------------------------
# MESSAGE RECEIPTS
# -------------------------
class MessageReceipt(models.Model):
    class Status(models.TextChoices):
        DELIVERED = "DELIVERED", "Delivered"
        READ = "READ", "Read"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="receipts",
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="message_receipts",
    )

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        db_index=True,
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("message", "user")
        indexes = [
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self):
        return f"{self.user} → {self.message_id} ({self.status})"

# -------------------------
# STATUS UPDATES (STORIES)
# -------------------------
class StatusUpdate(models.Model):
    class Type(models.TextChoices):
        TEXT = "TEXT", "Text"
        IMAGE = "IMAGE", "Image"
        VIDEO = "VIDEO", "Video"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="statuses",
    )

    type = models.CharField(
        max_length=10,
        choices=Type.choices,
        db_index=True,
    )

    content = models.JSONField()

    created_at = models.DateTimeField(auto_now_add=True)
    
    # 🔹 WhatsApp-style 24-hour deletion
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["user", "expires_at"]),
        ]

    def save(self, *args, **kwargs):
        # 🔹 Auto-set expiration (24 hours) for stories
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Status {self.id} by {self.user.username}"
