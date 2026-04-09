import os
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db.models.signals import post_save
from accounts.models import User, UserProfile, PrivacySettings, SecuritySettings, UserWallet
from accounts.signals import create_user_profile

class Command(BaseCommand):
    help = 'Clean Supabase and import data from data_migration.json'

    def handle(self, *args, **options):
        self.stdout.write("Cleaning Supabase database...")
        
        # Disable signals
        post_save.disconnect(receiver=create_user_profile, sender=User)
        self.stdout.write("Signals disconnected.")

        # Clear existing data in correct order
        models_to_clear = [
            UserProfile, PrivacySettings, SecuritySettings, UserWallet, User
        ]
        
        for model in models_to_clear:
            count = model.objects.all().delete()[0]
            self.stdout.write(f"Deleted {count} records from {model.__name__}")

        self.stdout.write("Running loaddata...")
        try:
            call_command('loaddata', 'data_migration.json')
            self.stdout.write(self.style.SUCCESS('Successfully imported all data to Supabase!'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Import failed: {str(e)}'))
        finally:
            # Reconnect signals (optional since process is ending, but good practice)
            post_save.connect(receiver=create_user_profile, sender=User)
