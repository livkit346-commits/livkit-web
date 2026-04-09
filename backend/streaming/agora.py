import time
from django.conf import settings
from agora_token_builder import RtcTokenBuilder


def generate_agora_token(channel_name, uid, role):
    """
    Generates a secure Agora RTC token.
    """
    try:
        app_id = settings.AGORA_APP_ID
        app_certificate = settings.AGORA_APP_CERTIFICATE

        expiration_time = 3600  # 1 hour
        current_timestamp = int(time.time())
        privilege_expired_ts = current_timestamp + expiration_time

        token = RtcTokenBuilder.buildTokenWithUid(
            app_id,
            app_certificate,
            channel_name,
            uid if isinstance(uid, int) else 0, # Ensure uid is integer
            role,
            privilege_expired_ts
        )

        print("[DEBUG] Agora token generated successfully")

        return token

    except Exception as e:
        print("[ERROR] Agora token generation failed:", e)
        raise
