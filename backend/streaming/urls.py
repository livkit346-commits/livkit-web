from django.urls import path
from .views import (
    CreateLiveStreamView,
    JoinLiveStreamView,
    LeaveLiveStreamView,
    StreamHeartbeatView,
    EndLiveStreamView,
    ActiveLiveStreamView,
    LiveFeedView,
    GiftCoinsView,
    CoHostRequestView,
    CoHostRespondView,
    CoHostListRequestsView,
    CoHostStatusView,
    SearchAPIView
)

urlpatterns = [
    path("create/", CreateLiveStreamView.as_view()),
    path("<uuid:stream_id>/join/", JoinLiveStreamView.as_view()),
    path("<uuid:stream_id>/leave/", LeaveLiveStreamView.as_view()),
    path("<uuid:stream_id>/heartbeat/", StreamHeartbeatView.as_view()),
    path("<uuid:stream_id>/end/", EndLiveStreamView.as_view()),
    path("active/", ActiveLiveStreamView.as_view(), name="active_live_stream"),
    path("feed/", LiveFeedView.as_view(), name="live_feed"),

    # New Routes
    path("search/", SearchAPIView.as_view(), name="search"),
    path("<uuid:stream_id>/gift/", GiftCoinsView.as_view(), name="gift_coins"),
    path("<uuid:stream_id>/cohost/requests/", CoHostListRequestsView.as_view(), name="cohost_list_requests"),
    path("<uuid:stream_id>/cohost/request/", CoHostRequestView.as_view(), name="cohost_request"),
    path("cohost/<int:request_id>/respond/", CoHostRespondView.as_view(), name="cohost_respond"),
    path("cohost/<int:request_id>/status/", CoHostStatusView.as_view(), name="cohost_status"),
]
