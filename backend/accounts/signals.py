from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, UserProfile, PrivacySettings, SecuritySettings


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
        PrivacySettings.objects.create(user=instance)
        SecuritySettings.objects.create(user=instance)
