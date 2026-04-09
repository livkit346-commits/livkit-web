from rest_framework import serializers
from django.utils import timezone
from .models import LiveStream


class LiveStreamSerializer(serializers.ModelSerializer):
    streamer_identifier = serializers.SerializerMethodField()
    feed_type = serializers.SerializerMethodField()

    class Meta:
        model = LiveStream
        fields = [
            "id",
            "channel_name",
            "streamer_identifier",
            "is_live",
            "started_at",
            "ended_at",
            "total_views",
            "total_earnings",
            "feed_type",
        ]

    def get_streamer_identifier(self, obj):
        try:
            streamer = obj.streamer
        except Exception:
            return "unknown_user"

        if not streamer:
            return "unknown_user"

        if hasattr(streamer, "email") and streamer.email:
            return streamer.email

        return str(streamer.id)


    def get_feed_type(self, obj):
        """
        Feed only supports LIVE streams.
        """
        if obj.is_live:
            return "live"
        return "hidden"
