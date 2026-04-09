from django.contrib import admin
from .models import (UserProfile, Follow, StreamBooking, PrivacySettings,
                     SecuritySettings, Referral, ReferralSettings, WalletTransaction)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name", "phone")
    search_fields = ("user__email", "display_name")

@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ("follower", "following", "created_at")

@admin.register(StreamBooking)
class StreamBookingAdmin(admin.ModelAdmin):
    list_display = ("user", "streamer", "created_at")

@admin.register(PrivacySettings)
class PrivacySettingsAdmin(admin.ModelAdmin):
    list_display = ("user", "is_private_account", "allow_comments", "allow_duet", "allow_download")
    search_fields = ("user__email",)

@admin.register(SecuritySettings)
class SecuritySettingsAdmin(admin.ModelAdmin):
    list_display = ("user", "two_factor_auth", "security_alerts")
    search_fields = ("user__email",)

@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ("referrer", "referred_user", "subscription_completed", "reward_given", "created_at")
    list_filter = ("reward_given", "subscription_completed")
    search_fields = ("referrer__username", "referred_user__username")

@admin.register(ReferralSettings)
class ReferralSettingsAdmin(admin.ModelAdmin):
    list_display = ("reward_referrer_usd", "reward_new_user_usd", "is_active")

@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ("user", "type", "amount_usd", "description", "created_at")
    list_filter = ("type",)
    search_fields = ("user__username", "description")
    readonly_fields = ("created_at",)
