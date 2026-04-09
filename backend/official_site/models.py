from django.db import models

# Create your models here.

class SubscriptionPlan(models.Model):
    PLAN_TYPES = (
        ('COIN', 'Coin Subscription'),
        ('APP', 'App Subscription'),
    )
    name = models.CharField(max_length=100)
    plan_type = models.CharField(max_length=10, choices=PLAN_TYPES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_months = models.IntegerField(default=1)
    benefits = models.TextField(help_text="Comma separated list of benefits")

    def __str__(self):
        return f"{self.name} - ${self.price}"

class TimeSubscriptionTier(models.Model):
    name = models.CharField(max_length=100, default="Premium Plan")
    duration_hours = models.IntegerField(help_text="Duration in hours (e.g. 6, 12, 48, 96, etc.)")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    benefits = models.TextField(blank=True, help_text="Comma separated list of features")
    is_active = models.BooleanField(default=True)
    discount_percentage = models.IntegerField(default=0, help_text="0-100")
    
    def get_final_price(self):
        import decimal
        if self.discount_percentage > 0:
            discount = self.price * decimal.Decimal(self.discount_percentage / 100.0)
            return self.price - discount
        return self.price

    def __str__(self):
        return f"{self.name} ({self.duration_hours}h) - ${self.price}"

class CoinPackage(models.Model):
    name = models.CharField(max_length=100, default="Coin Pack")
    coin_amount = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    bonus_coins = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.name} - {self.coin_amount} Coins for ${self.price}"

class PlatformPurchaseHistory(models.Model):
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name="platform_purchases")
    product_type = models.CharField(max_length=50, choices=(('SUBSCRIPTION', 'Subscription'), ('COIN', 'Coin Package')))
    product_name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, default="SUCCESS")
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} bought {self.product_name} (${self.amount})"

class VirtualGift(models.Model):
    name = models.CharField(max_length=100, unique=True)
    coin_cost = models.IntegerField()
    image_url = models.URLField(blank=True, null=True, help_text="URL to gift animation/image")
    css_icon_class = models.CharField(max_length=50, blank=True, null=True, help_text="e.g. bx-gift")
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['sort_order', 'coin_cost']

    def __str__(self):
        return f"{self.name} ({self.coin_cost} Coins)"
