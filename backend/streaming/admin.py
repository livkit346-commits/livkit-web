from django.contrib import admin
from .models import FallbackVideo, LiveStream, CoHostRequest

@admin.register(FallbackVideo)
class FallbackVideoAdmin(admin.ModelAdmin):
    list_display = ("title", "video_url", "is_active", "weight")
    list_editable = ("is_active", "weight")
    search_fields = ("title", "video_url")

# Optional: also register LiveStream for debugging
@admin.register(LiveStream)
class LiveStreamAdmin(admin.ModelAdmin):
    list_display = ("channel_name", "streamer", "is_live", "is_private", "started_at", "total_views")
    list_filter = ("is_live", "is_private")
    search_fields = ("channel_name", "streamer__email")

@admin.register(CoHostRequest)
class CoHostRequestAdmin(admin.ModelAdmin):
    list_display = ("stream", "viewer", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("stream__channel_name", "viewer__email")
