from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from chat.models import Message

class Command(BaseCommand):
    help = "Delete chat messages older than 3 months"

    def handle(self, *args, **kwargs):
        cutoff_date = timezone.now() - timedelta(days=90)
        deleted, _ = Message.objects.filter(
            created_at__lt=cutoff_date
        ).delete()

        self.stdout.write(
            self.style.SUCCESS(f"Deleted {deleted} old messages")
        )
