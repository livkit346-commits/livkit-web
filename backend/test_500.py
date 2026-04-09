import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.test import Client
import traceback

c = Client()
try:
    response = c.post('/sign_up', {
        'username': 'tester700', 
        'email': 'tester700@example.com', 
        'password': 'password', 
        'password_confirm': 'password'
    })
    print(f"Status Code: {response.status_code}")
    if response.status_code == 500:
        print(response.content.decode('utf-8'))
except Exception as e:
    traceback.print_exc()
