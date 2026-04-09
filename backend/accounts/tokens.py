from rest_framework_simplejwt.tokens import RefreshToken

from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.crypto import salted_hmac
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

class PasswordResetTokenGeneratorV2(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{user.password}{user.token_version}{timestamp}"

password_reset_token = PasswordResetTokenGeneratorV2()




def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)

    refresh['role'] = user.role
    refresh['is_banned'] = user.is_banned

    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


def create_admin_tokens(user):
    refresh = RefreshToken.for_user(user)

    refresh["role"] = user.role
    refresh["is_admin"] = True
    refresh["token_type"] = "admin"
    refresh["token_version"] = user.token_version

    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }

