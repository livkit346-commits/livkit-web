from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import UserWallet, EarningTransaction, PaymentAccount, PayoutLog, AdminWalletConfig
from django.db import transaction

class Command(BaseCommand):
    help = 'Processes pending balances to withdrawable and handles weekly payouts.'

    def handle(self, *args, **options):
        self.stdout.write("Starting Payout Processing...")
        
        # 1. Release Pending Funds
        self.release_pending_funds()
        
        # 2. Process Weekly Payouts (if it's the right day)
        # Note: In a real system, you'd check if today is the payout day from config
        self.process_automated_payouts()
        
        self.stdout.write(self.style.SUCCESS("Payout tasks completed successfully."))

    def release_pending_funds(self):
        now = timezone.now()
        pending_txs = EarningTransaction.objects.filter(status='pending', release_date__lte=now)
        
        count = 0
        for tx in pending_txs:
            with transaction.atomic():
                wallet = UserWallet.objects.select_for_update().get(user=tx.user)
                wallet.pending_balance -= tx.amount
                wallet.withdrawable_balance += tx.amount
                wallet.save()
                
                tx.status = 'released'
                tx.save()
                count += 1
        
        self.stdout.write(f"Released {count} transactions.")

    def process_automated_payouts(self):
        config = AdminWalletConfig.objects.first()
        if not config:
            return
            
        # Target users with enough balance and verified accounts
        eligible_wallets = UserWallet.objects.filter(
            withdrawable_balance__gte=config.min_withdrawal,
            is_frozen=False
        )
        
        count = 0
        for wallet in eligible_wallets:
            # Check for verified payment account
            account = PaymentAccount.objects.filter(user=wallet.user, is_verified=True).first()
            if not account:
                continue
                
            amount = wallet.withdrawable_balance
            # Optional: cap at max withdrawal
            if config.max_withdrawal > 0 and amount > config.max_withdrawal:
                amount = config.max_withdrawal
                
            with transaction.atomic():
                # Lock wallet
                wallet = UserWallet.objects.select_for_update().get(id=wallet.id)
                wallet.withdrawable_balance -= amount
                wallet.save()
                
                # Create Payout Log
                PayoutLog.objects.create(
                    user=wallet.user,
                    payment_account=account,
                    amount=amount,
                    status='processing'
                )
                count += 1
                
        self.stdout.write(f"Initiated {count} automated payouts.")
