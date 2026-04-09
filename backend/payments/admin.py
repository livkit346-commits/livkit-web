from django.contrib import admin
from .models import CoinPricing

@admin.register(CoinPricing)
class CoinPricingAdmin(admin.ModelAdmin):
    list_display = ("coin_amount", "price_usd", "price_ngn", "is_active", "created_at")
    list_editable = ("is_active", "price_usd", "price_ngn")
    search_fields = ("coin_amount",)
    list_filter = ("is_active",)
