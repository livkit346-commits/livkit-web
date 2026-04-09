from urllib.parse import parse_qs
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.conf import settings
from asgiref.sync import sync_to_async
import jwt
import logging

User = get_user_model()
logger = logging.getLogger("chat.middleware")


@sync_to_async
def get_user(user_id):
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return AnonymousUser()


class JWTAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        scope["user"] = AnonymousUser()

        # Try token from query params
        query_string = scope.get("query_string", b"").decode()
        params = parse_qs(query_string)
        token = params.get("token", [None])[0]

        # Fallback to cookie (for web dashboard)
        if not token:
            headers = dict(scope.get("headers", []))
            cookie_header = headers.get(b"cookie", b"").decode()
            if cookie_header:
                cookies = {k.strip(): v for k, v in [x.split('=', 1) for x in cookie_header.split(';') if '=' in x]}
                token = cookies.get("access")

        if token:
            from official_site.supabase_utils import verify_supabase_token
            try:
                # 1. Try internal Django SECRET_KEY (Legacy/Web)
                try:
                    payload = jwt.decode(
                        token,
                        settings.SECRET_KEY,
                        algorithms=["HS256"],
                    )
                    user_id = payload.get("user_id")
                except jwt.InvalidTokenError:
                    # 2. Try Supabase Token (Mobile/New)
                    payload = verify_supabase_token(token)
                    user_id_supabase = payload.get("sub") # Supabase uses 'sub' for UID
                    email = payload.get("email")
                    
                    # Map Supabase user to local Django user
                    user = await sync_to_async(User.objects.filter(email=email).first)()
                    user_id = user.id if user else None

                if user_id:
                    scope["user"] = await get_user(user_id)
                    logger.info(f"WebSocket JWT valid: user={scope['user']}")

            except Exception as e:
                logger.warning(f"WebSocket JWT invalid: {e}")

        return await self.app(scope, receive, send)
