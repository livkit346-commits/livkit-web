import os
import django
import firebase_admin
from firebase_admin import credentials, firestore

# 1. Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from accounts.models import User, UserProfile, UserWallet

# 2. Firebase Init
# Ensure you have your serviceAccountKey.json at the specified path
SERVICE_ACCOUNT_PATH = 'serviceAccountKey.json' 

if not os.path.exists(SERVICE_ACCOUNT_PATH):
    print(f"Error: {SERVICE_ACCOUNT_PATH} not found. Please provide it for migration.")
    exit(1)

cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
firebase_admin.initialize_app(cred)
db = firestore.client()

def migrate_users():
    print("Migrating Users and Profiles...")
    users_ref = db.collection(u'users')
    docs = users_ref.stream()

    for doc in docs:
        data = doc.to_dict()
        uid = doc.id
        email = data.get('email')
        username = data.get('username') or data.get('displayName') or f"user_{uid[:5]}"
        
        if not email:
            print(f"Skipping user {uid} (no email found)")
            continue

        # Create or update Django User
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'username': username,
                'is_active': True,
            }
        )

        if created:
            print(f"Created new user: {email}")
            # Initialize empty wallet
            UserWallet.objects.get_or_create(user=user)
        else:
            print(f"Updated existing user: {email}")

        # Update User Profile
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.display_name = data.get('username') or data.get('displayName', '')
        profile.bio = data.get('bio', '')
        profile.phone = data.get('phone', '')
        # Avatar link from Firestore
        # profile.avatar_url = data.get('profilepics', '') # Assuming we add an avatar_url field or handle storage separately
        profile.save()

    print("User migration complete.")

if __name__ == "__main__":
    migrate_users()
