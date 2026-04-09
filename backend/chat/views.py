from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Conversation, ConversationMember, Message
from .serializers import ConversationSerializer, MessageSerializer
from .permissions import IsConversationMember

from rest_framework.pagination import LimitOffsetPagination

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError

from django.views.decorators.csrf import csrf_exempt

from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
import json

from django.contrib.auth.decorators import login_required
from django.utils import timezone

from .models import FriendRequest

User = get_user_model()


from rest_framework.decorators import api_view



from rest_framework.decorators import api_view, permission_classes

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def get_or_create_friend_conversation(request):
    friend_id = request.data.get("friend_id")
    if not friend_id:
        return Response({"detail": "friend_id is required"}, status=400)

    user = request.user
    friend = User.objects.filter(id=friend_id).first()
    if not friend:
        return Response({"detail": "Friend not found"}, status=404)

    # Check if conversation exists
    conversation = (
        Conversation.objects.filter(
            type=Conversation.Type.PRIVATE,  # make sure 'PRIVATE' exists in Type
            members__user=user
        ).filter(members__user=friend)
        .first()
    )

    # Create if not exists
    if not conversation:
        conversation = Conversation.objects.create(
            type=Conversation.Type.PRIVATE,
            title=f"{user.username} & {friend.username}",
            created_by=user
        )
        ConversationMember.objects.bulk_create([
            ConversationMember(conversation=conversation, user=user),
            ConversationMember(conversation=conversation, user=friend),
        ])

    return Response({
        "id": str(conversation.id),
        "title": conversation.title,
        "members": [user.username, friend.username]  # optional
    })

# --------------------------------------------------
# AUTH HELPERS (UNCHANGED)
# --------------------------------------------------

def get_logged_in_user(request):
    auth_header = request.META.get("HTTP_AUTHORIZATION")
    if not auth_header:
        return None, JsonResponse({"error": "Authorization header missing"}, status=401)

    token = auth_header.split("Bearer ")[-1]
    try:
        validated_token = JWTAuthentication().get_validated_token(token)
        user = JWTAuthentication().get_user(validated_token)
        return user, None
    except TokenError:
        return None, JsonResponse({"error": "Invalid or expired token"}, status=401)


def jwt_required(view_func):
    """Decorator to enforce JWT auth for function-based views."""
    def wrapped(request, *args, **kwargs):
        jwt_auth = JWTAuthentication()
        try:
            user_auth_tuple = jwt_auth.authenticate(request)
            if user_auth_tuple is None:
                return JsonResponse(
                    {"error": "Authentication credentials were not provided."},
                    status=401
                )
            request.user = user_auth_tuple[0]
        except Exception:
            return JsonResponse({"error": "Invalid token"}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapped


# --------------------------------------------------
# FRIEND REQUESTS (UNCHANGED)
# --------------------------------------------------

@csrf_exempt
def pending_requests(request):
    if request.method != "GET":
        return JsonResponse({"error": "GET required"}, status=405)

    auth_header = request.META.get("HTTP_AUTHORIZATION")
    if not auth_header:
        return JsonResponse({"error": "Authorization header missing"}, status=401)

    token = auth_header.split("Bearer ")[-1]
    try:
        validated_token = JWTAuthentication().get_validated_token(token)
        user = JWTAuthentication().get_user(validated_token)
    except TokenError:
        return JsonResponse({"error": "Invalid or expired token"}, status=401)

    pending = FriendRequest.objects.filter(receiver=user, accepted__isnull=True)
    data = [
        {
            "id": fr.id,
            "sender_id": fr.sender.id,
            "sender_username": fr.sender.username,
            "sender_email": fr.sender.email,
        }
        for fr in pending
    ]
    return JsonResponse({"pending_requests": data})


@csrf_exempt
def respond_request(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    auth_header = request.META.get("HTTP_AUTHORIZATION")
    if not auth_header:
        return JsonResponse({"error": "Authorization header missing"}, status=401)

    token = auth_header.split("Bearer ")[-1]
    try:
        validated_token = JWTAuthentication().get_validated_token(token)
        user = JWTAuthentication().get_user(validated_token)
    except TokenError:
        return JsonResponse({"error": "Invalid or expired token"}, status=401)

    data = json.loads(request.body)
    fr_id = data.get("request_id")
    accept = data.get("accept")

    try:
        fr = FriendRequest.objects.get(id=fr_id, receiver=user)
        fr.accepted = accept
        fr.save()
        return JsonResponse({"success": True})
    except FriendRequest.DoesNotExist:
        return JsonResponse({"error": "Request not found"}, status=404)


@require_GET
def search_users(request):
    q = request.GET.get("q", "")
    users = User.objects.filter(username__icontains=q)[:10]
    results = [
        {"id": u.id, "username": u.username, "email": u.email}
        for u in users
    ]
    return JsonResponse({"results": results})


@csrf_exempt
def send_friend_request(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    auth_header = request.META.get("HTTP_AUTHORIZATION")
    if not auth_header:
        return JsonResponse({"error": "Authorization header missing"}, status=401)

    token = auth_header.split("Bearer ")[-1]
    try:
        validated_token = JWTAuthentication().get_validated_token(token)
        sender = JWTAuthentication().get_user(validated_token)
    except TokenError:
        return JsonResponse({"error": "Invalid or expired token"}, status=401)

    data = json.loads(request.body)
    receiver_id = data.get("user_id")

    if sender.id == receiver_id:
        return JsonResponse(
            {"error": "You cannot send a friend request to yourself"},
            status=400
        )

    try:
        receiver = User.objects.get(id=receiver_id)
    except User.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)

    existing = FriendRequest.objects.filter(
        sender=sender,
        receiver=receiver
    ).first()
    if existing:
        return JsonResponse({"error": "Request already sent"}, status=400)

    fr = FriendRequest.objects.create(
        sender=sender,
        receiver=receiver,
        accepted=None
    )
    return JsonResponse({"success": True, "request_id": fr.id})


@csrf_exempt
@require_GET
@jwt_required
def list_friends(request):
    user = request.user

    sent = FriendRequest.objects.filter(sender=user, accepted=True)
    received = FriendRequest.objects.filter(receiver=user, accepted=True)

    friends = []

    for fr in sent:
        friends.append({
            "id": fr.receiver.id,
            "username": fr.receiver.username,
            "email": fr.receiver.email,
        })

    for fr in received:
        friends.append({
            "id": fr.sender.id,
            "username": fr.sender.username,
            "email": fr.sender.email,
        })

    return JsonResponse({"friends": friends})


# --------------------------------------------------
# CHAT: MESSAGE HISTORY (WHATSAPP-STYLE FIX)
# --------------------------------------------------

class MessageListView(generics.ListAPIView):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated, IsConversationMember]
    pagination_class = LimitOffsetPagination

    def get_queryset(self):
        conversation_id = self.kwargs["conversation_id"]

        # ✅ Only active, non-deleted, non-expired messages
        return (
            Message.objects.filter(
                conversation_id=conversation_id,
                is_deleted=False,
            )
            .filter(
                expires_at__gt=timezone.now()
            )
            .select_related("sender")
            .order_by("created_at")  # 👈 WhatsApp order (old → new)
        )


# --------------------------------------------------
# CHAT LIST (UNCHANGED, ALREADY CORRECT)
# --------------------------------------------------

class ConversationListView(generics.ListAPIView):
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Conversation.objects.filter(
                members__user=self.request.user,
                is_active=True,
            )
            .distinct()
            .order_by("-last_message_at")
        )

# --------------------------------------------------
# CHAT MEDIA UPLOAD
# --------------------------------------------------

from django.core.files.storage import default_storage
import uuid
import os

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_chat_media(request):
    """
    Handle Image/Video uploads for Chat messages.
    Stores temporarily in Django media folder to be cached by receiving clients via IndexedDB.
    """
    if 'file' not in request.FILES:
        return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)

    file_obj = request.FILES['file']
    ext = os.path.splitext(file_obj.name)[1]
    filename = f"chat_media/{uuid.uuid4().hex}{ext}"

    # Save to configured default_storage (local MEDIA_ROOT)
    saved_path = default_storage.save(filename, file_obj)
    file_url = request.build_absolute_uri(default_storage.url(saved_path))

    return Response({
        "url": file_url,
        "name": file_obj.name,
        "size": file_obj.size,
        "type": file_obj.content_type
    }, status=status.HTTP_201_CREATED)

# --------------------------------------------------
# STATUS UPDATES (WHATSAPP-STYLE)
# --------------------------------------------------
from .models import StatusUpdate

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_statuses(request):
    """
    Get active statuses for the User and their network (Friends).
    Groups them nicely by user.
    """
    user = request.user
    
    # 1. Get friend IDs (from FriendRequest where accepted=True)
    sent_friend_ids = FriendRequest.objects.filter(sender=user, accepted=True).values_list('receiver_id', flat=True)
    recv_friend_ids = FriendRequest.objects.filter(receiver=user, accepted=True).values_list('sender_id', flat=True)
    friend_ids = list(sent_friend_ids) + list(recv_friend_ids)
    
    # 2. Add current user to see their own statuses
    allowed_user_ids = friend_ids + [user.id]

    # 3. Query Active Statuses
    active_statuses = StatusUpdate.objects.filter(
        user_id__in=allowed_user_ids,
        expires_at__gt=timezone.now()
    ).select_related('user').order_by('user_id', 'created_at')

    # Group by user
    grouped = {}
    for st in active_statuses:
        uid = st.user.id
        if uid not in grouped:
            grouped[uid] = {
                "user": {
                    "id": uid,
                    "username": st.user.username,
                    "avatar": f"https://ui-avatars.com/api/?name={st.user.username}&background=random"
                },
                "is_me": uid == user.id,
                "statuses": []
            }
        
        grouped[uid]["statuses"].append({
            "id": str(st.id),
            "type": st.type,
            "url": st.content.get("url") if isinstance(st.content, dict) else st.content,
            "text": st.content.get("text") if isinstance(st.content, dict) else "",
            "created_at": st.created_at.isoformat(),
            "expires_at": st.expires_at.isoformat()
        })
    
    # Sort groups: ME first, then others alphabetically or by most recent status
    results = list(grouped.values())
    results.sort(key=lambda x: (not x['is_me'], x['user']['username']))

    return Response({"results": results})

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_status(request):
    """
    Handle Image/Video/Text uploads for 24-hour Status.
    """
    user = request.user
    
    if 'file' in request.FILES:
        file_obj = request.FILES['file']
        ext = os.path.splitext(file_obj.name)[1]
        filename = f"status_media/{uuid.uuid4().hex}{ext}"

        saved_path = default_storage.save(filename, file_obj)
        file_url = request.build_absolute_uri(default_storage.url(saved_path))
        
        is_video = file_obj.content_type.startswith('video/')
        
        st = StatusUpdate.objects.create(
            user=user,
            type=StatusUpdate.Type.VIDEO if is_video else StatusUpdate.Type.IMAGE,
            content={"url": file_url}
        )
        return Response({"success": True, "id": str(st.id)}, status=status.HTTP_201_CREATED)
        
    elif 'text' in request.data:
        text = request.data['text']
        st = StatusUpdate.objects.create(
            user=user,
            type=StatusUpdate.Type.TEXT,
            content={"text": text}
        )
        return Response({"success": True, "id": str(st.id)}, status=status.HTTP_201_CREATED)
        
    return Response({"error": "No file or text provided"}, status=status.HTTP_400_BAD_REQUEST)
