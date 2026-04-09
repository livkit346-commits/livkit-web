from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
from .managers import UserManager




class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ('USER', 'User'),
        ('ADMIN_LIMITED', 'Limited Admin'),
        ('ADMIN_MAIN', 'Main Admin'),
        ('MASTER_ADMIN', 'Master Admin'),
    )

    username = models.CharField(
        max_length=30,
        unique=True,
        null=True,
        blank=True
    )


    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='USER')

    is_active = models.BooleanField(default=True)
    is_banned = models.BooleanField(default=False)

    # ⚠️ Legacy field (DO NOT USE FOR LOGIC ANYMORE)
    has_lifetime_access = models.BooleanField(default=False)

    date_joined = models.DateTimeField(default=timezone.now)

    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    token_version = models.IntegerField(default=0)

    # Referral system
    referral_code = models.CharField(max_length=20, unique=True, null=True, blank=True)
    referred_by = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='referrals_made'
    )
    total_referrals = models.IntegerField(default=0)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email

    # ✅ SINGLE SOURCE OF TRUTH
    @property
    def lifetime_access(self):
        """
        True if user has an active entitlement
        (Stripe OR Play Store)
        """
        return hasattr(self, "entitlement") and self.entitlement.is_active



class UserProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile"
    )

    display_name = models.CharField(
        max_length=100,
        blank=True
    )

    bio = models.TextField(
        blank=True
    )

    phone = models.CharField(
        max_length=20,
        blank=True
    )

    avatar = models.ImageField(
        upload_to="avatars/",
        blank=True,
        null=True
    )

    updated_at = models.DateTimeField(auto_now=True)
    banner_image = models.ImageField(
        upload_to="banners/",
        blank=True,
        null=True
    )

    def __str__(self):
        return f"{self.user.email} profile"


class Follow(models.Model):
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name="following")
    following = models.ForeignKey(User, on_delete=models.CASCADE, related_name="followers")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("follower", "following")

    def __str__(self):
        return f"{self.follower} follows {self.following}"


class StreamBooking(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bookings")
    streamer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="booked_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "streamer")

    def __str__(self):
        return f"{self.user} booked {self.streamer}'s stream"

# ==========================================
# APP-STYLE SETTINGS MODELS
# ==========================================

class PrivacySettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="privacy_settings")
    is_private_account = models.BooleanField(default=False)
    allow_comments = models.BooleanField(default=True)
    allow_duet = models.BooleanField(default=True)
    allow_download = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.email} - Privacy Settings"

class SecuritySettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="security_settings")
    two_factor_auth = models.BooleanField(default=False)
    security_alerts = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.email} - Security Settings"

# ==========================================
# WALLET & PAYOUT MODELS
# ==========================================

class PaymentAccount(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="payment_accounts")
    account_type = models.CharField(max_length=50, choices=[('bank', 'Bank Account'), ('mobile', 'Mobile Money'), ('paypal', 'PayPal')])
    account_name = models.CharField(max_length=255)
    account_number = models.CharField(max_length=255)
    bank_name = models.CharField(max_length=255, blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.account_type}"

class WithdrawalRequest(models.Model):
    # Keeping this so we don't break old migrations, but we won't use it actively going forward.
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('paid', 'Paid')
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="withdrawal_requests")
    payment_account = models.ForeignKey(PaymentAccount, on_delete=models.SET_NULL, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_notes = models.TextField(blank=True, null=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"${self.amount} by {self.user.email} ({self.status})"

class AdminWalletConfig(models.Model):
    withdrawal_delay_days = models.IntegerField(default=7)
    min_withdrawal = models.DecimalField(max_digits=10, decimal_places=2, default=50.00)
    max_withdrawal = models.DecimalField(max_digits=10, decimal_places=2, default=10000.00, blank=True, null=True)
    allow_unlimited_withdrawals = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        self.pk = 1 # enforce singleton
        super(AdminWalletConfig, self).save(*args, **kwargs)

    @classmethod
    def get_config(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
        
    def __str__(self):
        return "Global Wallet Configuration"

class UserWallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="wallet")
    pending_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    withdrawable_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    balance_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  # referral & general USD rewards
    is_frozen = models.BooleanField(default=False)
    is_flagged = models.BooleanField(default=False)

    @property
    def total_balance(self):
        return self.pending_balance + self.withdrawable_balance
        
    def __str__(self):
        return f"{self.user.email}'s Wallet - Total: ${self.total_balance}"

class EarningTransaction(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Release'),
        ('released', 'Released to Withdrawable'),
        ('cancelled', 'Cancelled')
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="wallet_earnings")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    source = models.CharField(max_length=255) # e.g., "Gift - Rose", "Subscription"
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    release_date = models.DateTimeField()
    
    def __str__(self):
        return f"${self.amount} directly to {self.user.email} (Source: {self.source})"

class PayoutLog(models.Model):
    STATUS_CHOICES = [
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="payouts")
    payment_account = models.ForeignKey('PaymentAccount', on_delete=models.SET_NULL, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='processing')
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    transaction_reference = models.CharField(max_length=255, blank=True, null=True)
    
    def __str__(self):
        return f"Payout: ${self.amount} for {self.user.email} ({self.status})"


# ==========================================
# REFERRAL SYSTEM MODELS
# ==========================================

class ReferralSettings(models.Model):
    """Singleton model — only one record (pk=1). Admin controls reward amounts."""
    reward_new_user_usd = models.DecimalField(max_digits=8, decimal_places=2, default=0.50)
    reward_referrer_usd = models.DecimalField(max_digits=8, decimal_places=2, default=1.00)
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        self.pk = 1  # enforce singleton
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"Referral Settings (referrer=${self.reward_referrer_usd}, new user=${self.reward_new_user_usd}, active={self.is_active})"


class Referral(models.Model):
    """Tracks each referral relationship and its reward status."""
    referrer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='given_referrals')
    referred_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_referral')
    reward_given = models.BooleanField(default=False)
    subscription_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('referrer', 'referred_user')

    def __str__(self):
        return f"{self.referrer.username} → {self.referred_user.username} (reward_given={self.reward_given})"


class WalletTransaction(models.Model):
    """Unified transaction ledger for all USD wallet activity."""
    TYPE_CHOICES = [
        ('referral_reward', 'Referral Reward'),
        ('subscription', 'Subscription'),
        ('gift', 'Gift Received'),
        ('withdrawal', 'Withdrawal'),
        ('other', 'Other'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wallet_transactions')
    type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    amount_usd = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} | {self.type} | ${self.amount_usd}"
