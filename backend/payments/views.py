import json
import stripe
from django.conf import settings
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model

from .models import Entitlement, PaymentLog, CoinPricing, CoinWallet, CoinLedger
from accounts.permissions import IsAuthenticatedAndNotBanned
from rest_framework.generics import ListAPIView
from rest_framework.serializers import ModelSerializer

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

# ---------- STRIPE ---------- #

stripe.api_key = settings.STRIPE_SECRET_KEY

class StripeCreateCheckoutView(APIView):
    permission_classes = [IsAuthenticated, IsAuthenticatedAndNotBanned]

    def post(self, request):
        user = request.user

        # already paid → don't allow repeat payment
        entitlement, _ = Entitlement.objects.get_or_create(user=user)
        if entitlement.is_active:
            return Response({
                "already_paid": True,
                "message": "You’ve already unlocked premium content!"
            })


        session = stripe.checkout.Session.create(
            mode="payment",
            success_url=settings.FRONTEND_SUCCESS_URL,
            cancel_url=settings.FRONTEND_CANCEL_URL,
            customer_email=user.email,
            line_items=[
                {
                    "price": settings.STRIPE_PRICE_ID,
                    "quantity": 1,
                }
            ],
            metadata={"user_id": user.id}
        )

        return Response({"checkout_url": session.url})


# ---------- STRIPE WEBHOOK ---------- #


@csrf_exempt
def stripe_webhook(request):
    print(">>>>>>> WEBHOOK HIT")

    try:
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.STRIPE_WEBHOOK_SECRET
        )

        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            print("SESSION DATA:", session)

            user_id = session.get("metadata", {}).get("user_id")
            transaction_id = session["id"]

            print("USER ID:", user_id)
            print("TX ID:", transaction_id)

            if not user_id or not transaction_id:
                print("⚠️ Missing user_id or transaction_id")
                return HttpResponse(status=200)

            User = get_user_model()
            user = User.objects.get(id=user_id)

            entitlement, _ = Entitlement.objects.get_or_create(user=user)
            entitlement.activate("stripe", transaction_id)

        return HttpResponse(status=200)

    except Exception as e:
        print("❌ WEBHOOK CRASH:", str(e))
        return HttpResponse(status=500)





# ---------- GOOGLE PLAY VERIFY ---------- #

from google.oauth2 import service_account
from googleapiclient.discovery import build


class GoogleVerifyPurchaseView(APIView):
    permission_classes = [IsAuthenticated, IsAuthenticatedAndNotBanned]

    def post(self, request):
        user = request.user

        entitlement, _ = Entitlement.objects.get_or_create(user=user)
        if entitlement.is_active:
            return Response({
                "already_paid": True,
                "message": "You’ve already unlocked premium content!"
            }, status=200)



        purchase_token = request.data.get("purchaseToken")
        product_id = request.data.get("productId")
        package_name = request.data.get("packageName")

        if not (purchase_token and product_id and package_name):
            return Response({"error": "Missing fields"}, status=400)

        credentials = service_account.Credentials.from_service_account_file(
            settings.GOOGLE_SERVICE_ACCOUNT_FILE,
            scopes=["https://www.googleapis.com/auth/androidpublisher"],
        )

        service = build("androidpublisher", "v3", credentials=credentials)
        result = service.purchases().products().get(
            packageName=package_name,
            productId=product_id,
            token=purchase_token
        ).execute()

        # Google's response
        purchase_state = result.get("purchaseState")   # 0 = Purchased
        order_id = result.get("orderId")

        if purchase_state != 0:
            return Response({"error": "Purchase not valid"}, status=400)

        entitlement.activate("playstore", order_id)

        PaymentLog.objects.create(
            user=user,
            provider="playstore",
            event="purchase.verified",
            reference=order_id,
            payload=result
        )

        return Response({"detail": "Access granted"})


# ---------- COIN PURCHASING ---------- #

class CoinPricingSerializer(ModelSerializer):
    class Meta:
        model = CoinPricing
        fields = ['id', 'coin_amount', 'price_usd', 'price_ngn']

class CoinPricingListView(ListAPIView):
    queryset = CoinPricing.objects.filter(is_active=True).order_by('price_usd')
    serializer_class = CoinPricingSerializer
    permission_classes = [IsAuthenticated, IsAuthenticatedAndNotBanned]

class BuyCoinsView(APIView):
    permission_classes = [IsAuthenticated, IsAuthenticatedAndNotBanned]

    def post(self, request):
        package_id = request.data.get("package_id")
        try:
            package = CoinPricing.objects.get(id=package_id, is_active=True)
            wallet, _ = CoinWallet.objects.get_or_create(user=request.user)
            
            # Simulate a successful purchase and add coins
            CoinLedger.objects.create(
                wallet=wallet,
                amount=package.coin_amount,
                transaction_type="purchase",
                reference=f"buy_pkg_{package.id}"
            )
            
            return Response({
                "message": f"Successfully purchased {package.coin_amount} coins!", 
                "new_balance": wallet.balance
            })
        except CoinPricing.DoesNotExist:
            return Response({"error": "Invalid or inactive package"}, status=400)
