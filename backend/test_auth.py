import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from accounts.serializers import RegisterSerializer
from django.contrib.auth import authenticate
from accounts.models import User

payload = {
    "username": "cmd_test_user",
    "email": "cmd_test@example.com",
    "password": "cmd_password123",
}

print("Testing Registration...")
try:
    s = RegisterSerializer(data=payload)
    if s.is_valid(raise_exception=True):
        u = s.save()
        print("User created:", u)
except Exception as e:
    import traceback
    traceback.print_exc()

print("\nTesting Login...")
try:
    u2 = authenticate(email="cmd_test@example.com", password="cmd_password123")
    print("Authenticated user:", u2)
except Exception as e:
    import traceback
    traceback.print_exc()
