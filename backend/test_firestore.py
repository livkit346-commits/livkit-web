import os
import django
import sys

# Setup Django environment
sys.path.append(r"C:\Users\Hp\LivKit\Website\backend")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

import firebase_admin
from firebase_admin import firestore

try:
    db = firestore.client()
    collections = db.collections()
    for coll in collections:
        print(f"Found collection: {coll.id}")
    print("SUCCESS: Firestore API is enabled and accessible!")
except Exception as e:
    print(f"FAILED: {e}")
