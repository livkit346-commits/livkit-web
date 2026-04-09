import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone
from decimal import Decimal


User = settings.AUTH_USER_MODEL


class LiveStream(models.Model):
    """
    Represents a single live session.
    One streamer, many viewers.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    streamer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="live_streams"
    )


    title = models.CharField(max_length=255, blank=True, null=True)
    category = models.CharField(max_length=100, blank=True, null=True)
    channel_name = models.CharField(max_length=255, unique=True)
    
    allow_chat = models.BooleanField(default=True)
    allow_multiguest = models.BooleanField(default=False)
    thumbnail = models.ImageField(upload_to="stream_thumbnails/", blank=True, null=True)
    
    is_private = models.BooleanField(default=False)
    password = models.CharField(max_length=50, blank=True, null=True)
    private_token = models.CharField(max_length=64, unique=True, null=True, blank=True)
    requires_approval = models.BooleanField(default=False)
    share_link = models.URLField(blank=True, null=True)

    is_live = models.BooleanField(default=False)

    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    total_views = models.PositiveIntegerField(default=0)

    total_earnings = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00")
    )

    created_at = models.DateTimeField(auto_now_add=True)

    last_heartbeat = models.DateTimeField(null=True, blank=True)

    @property
    def viewer_count(self):
        return self.view_sessions.filter(is_active=True).count()

    def __str__(self):
        return f"{self.channel_name} ({self.streamer})"


class LiveViewSession(models.Model):
    stream = models.ForeignKey(
        LiveStream,
        on_delete=models.CASCADE,
        related_name="view_sessions"
    )

    viewer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="viewed_streams"
    )

    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)

    last_heartbeat = models.DateTimeField(auto_now_add=True)

    active_seconds = models.PositiveIntegerField(default=0)

    minutes_watched = models.PositiveIntegerField(default=0)

    earnings_generated = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00")
    )

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.viewer} on {self.stream}"

    def force_end(self, reason="unknown"):
        self.left_at = timezone.now()
        self.is_active = False

        self.minutes_watched = max(0, self.active_seconds // 60)

        print(
            f"[ANTI-FRAUD] Session force-ended "
            f"(viewer={self.viewer}, reason={reason})"
        )

        self.save()

class FallbackVideo(models.Model):
    title = models.CharField(max_length=255)
    video_url = models.URLField()
    weight = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)


class CoHostRequest(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("ended", "Ended"),
    )

    stream = models.ForeignKey(LiveStream, on_delete=models.CASCADE, related_name="cohost_requests")
    viewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="cohost_requests")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("stream", "viewer", "status")

    def __str__(self):
        return f"{self.viewer} requesting to co-host {self.stream.channel_name}"


class JoinRequest(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )

    stream = models.ForeignKey(LiveStream, on_delete=models.CASCADE, related_name="join_requests")
    viewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="join_requests")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("stream", "viewer")

    def __str__(self):
        return f"{self.viewer} join request for {self.stream.channel_name} ({self.status})"


class InvitedUser(models.Model):
    stream = models.ForeignKey(LiveStream, on_delete=models.CASCADE, related_name="invited_users")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="stream_invitations")
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_invitations")
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("stream", "user")

    def __str__(self):
        return f"{self.user} invited to {self.stream.channel_name} by {self.invited_by}"
