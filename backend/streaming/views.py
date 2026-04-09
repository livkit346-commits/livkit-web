import random
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from decimal import Decimal
from agora_token_builder import RtcTokenBuilder

from .models import LiveStream, LiveViewSession
from .serializers import LiveStreamSerializer
from .agora import generate_agora_token
from django.db.models import Q
from .models import LiveStream, LiveViewSession, FallbackVideo, CoHostRequest
from payments.models import CoinWallet, CoinLedger, StreamEarning
from accounts.models import User
from django.db import transaction
from django.db.models import F, Q

MIN_PAYABLE_MINUTES = 2



HEARTBEAT_INTERVAL = 30  # seconds
HEARTBEAT_TIMEOUT = 60   # seconds


AGORA_ROLE_PUBLISHER = 1
AGORA_ROLE_SUBSCRIBER = 2


class CreateLiveStreamView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        print("[DEBUG] Create stream requested by:", user.id)

        channel_name = f"live_{user.id}_{int(timezone.now().timestamp())}"
        title = request.data.get("title", "")
        category = request.data.get("category", "")
        is_private = request.data.get("is_private", False)
        password = request.data.get("password", "")
        requires_approval = request.data.get("requires_approval", False)
        allow_chat = request.data.get("allow_chat", True)
        allow_multiguest = request.data.get("allow_multiguest", False)

        import secrets
        private_token = secrets.token_urlsafe(16) if is_private else None

        stream = LiveStream.objects.create(
            streamer=user,
            title=title,
            category=category,
            channel_name=channel_name,
            is_live=True,
            is_private=is_private,
            password=password,
            private_token=private_token,
            requires_approval=requires_approval,
            allow_chat=allow_chat,
            allow_multiguest=allow_multiguest,
            started_at=timezone.now()
        )

        try:
            token = generate_agora_token(
                channel_name=channel_name,
                uid=0,
                role=AGORA_ROLE_PUBLISHER
            )
        except Exception as e:
            print("[AGORA ERROR]", str(e))
            stream.delete()
            return Response(
                {"detail": "Agora token error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Generate share link
        if is_private:
            share_link = f"https://livkit.onrender.com/live/private/{private_token}/"
        else:
            share_link = f"https://livkit.onrender.com/live/{stream.id}"
            
        stream.share_link = share_link
        stream.save(update_fields=["share_link"])

        try:
            stream_data = LiveStreamSerializer(stream).data
            stream_data["share_link"] = share_link
            stream_data["is_private"] = is_private
        except Exception as e:
            print("[SERIALIZER ERROR]", e)
            raise


        return Response(
            {
                "stream": stream_data,
                "agora_token": token,
                "channel_name": channel_name,
                "private_token": private_token,
            },
            status=status.HTTP_201_CREATED
        )






class LeaveLiveStreamView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, stream_id):
        user = request.user

        try:
            session = LiveViewSession.objects.get(
                stream_id=stream_id,
                viewer=user,
                is_active=True
            )
        except LiveViewSession.DoesNotExist:
            return Response(
                {"detail": "Session not found"},
                status=status.HTTP_400_BAD_REQUEST
            )

        session.force_end(reason="viewer_left")

        minutes = session.active_seconds // 60
        session.minutes_watched = minutes

        if minutes < MIN_PAYABLE_MINUTES:
            session.save(update_fields=["minutes_watched"])
            return Response(
                {"detail": "Left stream (no payout)"},
                status=status.HTTP_200_OK
            )

        pay_per_minute = Decimal(str(random.uniform(0.05, 0.20)))
        earnings = Decimal(minutes) * pay_per_minute

        session.earnings_generated = earnings
        session.save(update_fields=[
            "minutes_watched",
            "earnings_generated"
        ])

        stream = session.stream
        stream.total_earnings = (stream.total_earnings or 0) + earnings

        stream.save(update_fields=["total_earnings"])

        return Response(
            {
                "detail": "Left stream successfully",
                "minutes": minutes,
                "earnings": earnings,
            },
            status=status.HTTP_200_OK
        )



class StreamHeartbeatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, stream_id):
        user = request.user

        try:
            session = LiveViewSession.objects.get(
                stream_id=stream_id,
                viewer=user,
                is_active=True,
                left_at__isnull=True
            )
        except LiveViewSession.DoesNotExist:
            return Response(
                {"detail": "No active session"},
                status=status.HTTP_400_BAD_REQUEST
            )

        now = timezone.now()
        delta = (now - session.last_heartbeat).total_seconds()

        if delta > HEARTBEAT_TIMEOUT:
            session.force_end(reason="heartbeat_timeout")
            return Response(
                {"detail": "Session expired"},
                status=status.HTTP_410_GONE
            )

        session.active_seconds += HEARTBEAT_INTERVAL
        session.last_heartbeat = now
        session.save(update_fields=["active_seconds", "last_heartbeat"])

        return Response(
            {
                "status": "ok",
                "active_seconds": session.active_seconds,
            },
            status=status.HTTP_200_OK
        )


class EndLiveStreamView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, stream_id):
        user = request.user

        with transaction.atomic():

            try:
                stream = LiveStream.objects.select_for_update().get(
                    id=stream_id,
                    streamer=user,
                    is_live=True
                )
            except LiveStream.DoesNotExist:
                return Response(
                    {"detail": "Stream not found or already ended"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # End stream
            stream.is_live = False
            stream.ended_at = timezone.now()
            stream.save(update_fields=["is_live", "ended_at"])

            active_sessions = LiveViewSession.objects.select_for_update().filter(
                stream=stream,
                is_active=True
            )

            total_earnings = Decimal("0.00")

            for session in active_sessions:

                session.force_end(reason="stream_ended")

                minutes = session.active_seconds // 60
                session.minutes_watched = minutes

                earnings = Decimal("0.00")

                if minutes >= MIN_PAYABLE_MINUTES:
                    pay_per_minute = Decimal(str(random.uniform(0.05, 0.20)))
                    earnings = Decimal(minutes) * pay_per_minute

                session.earnings_generated = earnings
                session.save(update_fields=["is_active", "ended_at", "minutes_watched", "earnings_generated"])

                total_earnings += earnings

            # Atomic earnings update
            stream.total_earnings = F("total_earnings") + total_earnings
            stream.save(update_fields=["total_earnings"])
            stream.refresh_from_db()

            print(f"[DEBUG] Stream {stream.id} ended. Earnings: {stream.total_earnings}")

        return Response(
            {
                "detail": "Live stream ended",
                "total_earnings": stream.total_earnings,
                "total_views": stream.total_views,
            },
            status=status.HTTP_200_OK
        )

class JoinLiveStreamView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, stream_id):
        user = request.user

        try:
            stream = LiveStream.objects.get(id=stream_id, is_live=True)
        except LiveStream.DoesNotExist:
            return Response(
                {"detail": "Stream not available"},
                status=status.HTTP_404_NOT_FOUND
            )

        if stream.streamer == user:
            return Response(
                {"detail": "Streamer cannot join own stream"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if stream.is_private:
            password = request.data.get("password", "")
            if stream.password and stream.password != password:
                return Response({"detail": "Incorrect password for private stream"}, status=status.HTTP_403_FORBIDDEN)

        LiveViewSession.objects.filter(
            stream=stream,
            viewer=user,
            is_active=True
        ).delete()

        session = LiveViewSession.objects.create(
            stream=stream,
            viewer=user
        )

        stream.total_views += 1
        stream.save(update_fields=["total_views"])

        try:
            token = generate_agora_token(
                channel_name=stream.channel_name,
                uid=user.id,
                role=AGORA_ROLE_SUBSCRIBER
            )
        except Exception as e:
            print("[AGORA ERROR]", str(e))
            return Response(
                {"detail": "Token generation failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {
                "stream_id": str(stream.id),
                "channel_name": stream.channel_name,
                "agora_token": token,
                "heartbeat_interval": HEARTBEAT_INTERVAL,
            },
            status=status.HTTP_200_OK
        )


class ActiveLiveStreamView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active_streams = LiveStream.objects.filter(is_live=True).order_by("-started_at")
        serializer = LiveStreamSerializer(active_streams, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class LiveFeedView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Filter: If it's private, maybe only show to booked people? Or we show it, but require password to enter.
        # Let's show public streams, plus streams from people they follow or book.
        live_streams = LiveStream.objects.filter(is_live=True).order_by("-started_at")
        
        # Sort so follows/bookings are prioritized
        prioritized = []
        others = []
        
        for stream in live_streams:
            is_followed = stream.streamer.followers.filter(follower=user).exists()
            is_booked = stream.streamer.booked_by.filter(user=user).exists()
            
            if is_followed or is_booked:
                prioritized.append(stream)
            elif not stream.is_private:
                others.append(stream)
                
        # Combine
        final_streams = prioritized + others

        for stream in live_streams:
            serialized = LiveStreamSerializer(stream).data

            # 🔥 Generate PREVIEW subscriber token
            preview_token = generate_agora_token(
                channel_name=stream.channel_name,
                uid=0,
                role=AGORA_ROLE_SUBSCRIBER
            )

            serialized["agora_token"] = preview_token
            live_data.append(serialized)

        fallback_videos = [
            {
                "type": "fallback",
                "title": video.title,
                "video_url": video.video_url,
            }
            for video in FallbackVideo.objects.filter(is_active=True)
        ]

        return Response({
            "live_streams": live_data,
            "fallbacks": fallback_videos,
        })


class GiftCoinsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, stream_id):
        user = request.user
        amount = int(request.data.get("amount", 0))

        if amount <= 0:
            return Response({"error": "Invalid gift amount"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            try:
                wallet = CoinWallet.objects.select_for_update().get(user=user)
            except CoinWallet.DoesNotExist:
                return Response({"error": "No coin wallet found"}, status=status.HTTP_400_BAD_REQUEST)

            if wallet.balance < amount:
                return Response({"error": "Insufficient coins"}, status=status.HTTP_400_BAD_REQUEST)

            try:
                stream = LiveStream.objects.get(id=stream_id, is_live=True)
            except LiveStream.DoesNotExist:
                return Response({"error": "Stream not active"}, status=status.HTTP_404_NOT_FOUND)

            # Deduct from viewer
            wallet.deduct(amount)

            CoinLedger.objects.create(
                user=user,
                action="gift",
                amount=amount
            )

            # Add to streamer earnings
            earning, _ = StreamEarning.objects.get_or_create(
                streamer=stream.streamer,
                stream_id=str(stream.id),
                defaults={'payout_amount': 0}
            )
            earning.gifts_received = F("gifts_received") + amount
            earning.payout_amount = F("payout_amount") + (amount * 10) # arbitrary flat cents value per coin
            earning.save()

            # Refresh wallet to get the balance after deduction
            wallet.refresh_from_db()
            new_balance = wallet.balance

        return Response({"status": "gifted", "amount": amount, "new_balance": new_balance}, status=status.HTTP_200_OK)


class CoHostRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, stream_id):
        user = request.user
        try:
            stream = LiveStream.objects.get(id=stream_id, is_live=True)
        except LiveStream.DoesNotExist:
            return Response({"error": "Stream not found or inactive"}, status=status.HTTP_404_NOT_FOUND)

        if stream.streamer == user:
            return Response({"error": "Streamer cannot request co-host"}, status=status.HTTP_400_BAD_REQUEST)

        req, created = CoHostRequest.objects.get_or_create(
            stream=stream,
            viewer=user,
            status="pending"
        )
        return Response({"status": "requested", "request_id": req.id}, status=status.HTTP_201_CREATED)


class CoHostRespondView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, request_id):
        user = request.user
        action = request.data.get("action") # "accept" or "reject"
        
        try:
            cohost_req = CoHostRequest.objects.get(id=request_id, stream__streamer=user, status="pending")
        except CoHostRequest.DoesNotExist:
            return Response({"error": "Request not found or unauthorized"}, status=status.HTTP_404_NOT_FOUND)

        if action == "accept":
            cohost_req.status = "accepted"
            cohost_req.save()
            return Response({"status": "accepted"}, status=status.HTTP_200_OK)
        else:
            cohost_req.status = "rejected"
            cohost_req.save()
            return Response({"status": "rejected"}, status=status.HTTP_200_OK)


class CoHostListRequestsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, stream_id):
        user = request.user
        try:
            stream = LiveStream.objects.get(id=stream_id, streamer=user, is_live=True)
        except LiveStream.DoesNotExist:
            return Response({"error": "Stream not found or unauthorized"}, status=status.HTTP_404_NOT_FOUND)

        requests = CoHostRequest.objects.filter(stream=stream, status="pending").order_by('created_at')
        data = []
        for req in requests:
            avatar_url = ""
            if hasattr(req.viewer, 'profile'):
                if req.viewer.profile.avatar:
                    avatar_url = req.viewer.profile.avatar.url
                else:
                    avatar_url = f"https://ui-avatars.com/api/?name={req.viewer.username}"
            data.append({
                "id": req.id,
                "viewer_id": req.viewer.id,
                "viewer_username": req.viewer.username,
                "viewer_avatar": avatar_url,
                "created_at": req.created_at
            })
        return Response({"requests": data}, status=status.HTTP_200_OK)


class CoHostStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, request_id):
        user = request.user
        try:
            cohost_req = CoHostRequest.objects.get(id=request_id, viewer=user)
        except CoHostRequest.DoesNotExist:
            return Response({"error": "Request not found"}, status=status.HTTP_404_NOT_FOUND)

        response_data = {"status": cohost_req.status}
        
        if cohost_req.status == "accepted":
            try:
                token = generate_agora_token(
                    channel_name=cohost_req.stream.channel_name,
                    uid=cohost_req.viewer.id,
                    role=AGORA_ROLE_PUBLISHER
                )
                response_data["agora_token"] = token
            except Exception as e:
                return Response({"detail": "Token error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(response_data, status=status.HTTP_200_OK)


class SearchAPIView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        query = request.query_params.get("q", "")
        if not query:
            return Response({"users": [], "streams": []}, status=status.HTTP_200_OK)
            
        users = User.objects.filter(
            Q(email__icontains=query) | Q(username__icontains=query)
        )[:10]

        streams = LiveStream.objects.filter(
            Q(channel_name__icontains=query),
            is_live=True,
            is_private=False
        )[:10]

        return Response({
            "users": [{"id": u.id, "username": u.username, "email": u.email} for u in users],
            "streams": [LiveStreamSerializer(s).data for s in streams]
        }, status=status.HTTP_200_OK)
