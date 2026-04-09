from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from accounts import backends
from .auth import jwt_required
from django.conf import settings
from django.contrib.auth import authenticate
from accounts.tokens import get_tokens_for_user
from accounts.serializers import RegisterSerializer
from accounts.models import PrivacySettings, SecuritySettings

API_BASE = "https://livkit.onrender.com/api/auth"



def sign_in(request):
    if request.method == "POST":
        id_token = request.POST.get("id_token")
        
        # If logging in via Supabase ID Token (JWT)
        if id_token:
            from .supabase_utils import verify_supabase_token
            from django.contrib.auth import get_user_model
            try:
                decoded_token = verify_supabase_token(id_token)
                # Supabase tokens use 'sub' for the user ID and 'email' in the payload
                uid = decoded_token.get('sub')
                email = decoded_token.get('email', '')
                
                # Link Supabase Account to a local Django User by Email
                User = get_user_model()
                user = User.objects.filter(email=email).first()
                if not user:
                    # Create a new local user if it doesn't exist
                    # We store the Supabase UID as the username or in a separate field (here we use username for simplicity)
                    user = User.objects.create(username=uid, email=email, role='USER')
                    user.set_unusable_password()
                    user.save()
                
                # 🚨 WEBSITE ROLE CHECK 🚨
                if getattr(user, 'role', 'USER') not in ['USER', 'ADMIN_MAIN', 'MASTER_ADMIN']:
                    # Restricted roles (like LIMITED_ADMIN) should use the Admin Portal
                    return render(request, "sign-in.html", {
                        "error": "Access Denied: Please use the Admin Portal for your role."
                    })

                if getattr(user, 'is_banned', False):
                    return render(request, "sign-in.html", {"error": "Account banned"})

                tokens = get_tokens_for_user(user)
                response = redirect("dashboard")
                response.set_cookie("access", tokens["access"], httponly=True, samesite="Lax")
                response.set_cookie("refresh", tokens["refresh"], httponly=True, samesite="Lax")
                return response
            except Exception as e:
                return render(request, "sign-in.html", {"error": f"Supabase Auth Error: {str(e)}"})

        # Fallback to legacy Django auth
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(email=email, password=password)

        if not user or not user.is_active:
            return render(request, "sign-in.html", {
                "error": "Invalid credentials"
            })

        if getattr(user, 'is_banned', False):
            return render(request, "sign-in.html", {
                "error": "Account banned"
            })

        from django.utils import timezone
        if getattr(user, 'suspended_until', None) and user.suspended_until > timezone.now():
            return render(request, "sign-in.html", {
                "error": f"Account suspended until {user.suspended_until.strftime('%Y-%m-%d %H:%M')}"
            })

        tokens = get_tokens_for_user(user)
        response = redirect("dashboard")

        response.set_cookie("access", tokens["access"], httponly=True, samesite="Lax")
        response.set_cookie("refresh", tokens["refresh"], httponly=True, samesite="Lax")

        return response

    return render(request, "sign-in.html")

def sign_up(request):
    if request.method == "POST":
        id_token = request.POST.get("id_token")
        
        # If signing up via Supabase Auth
        if id_token:
            from .supabase_utils import verify_supabase_token
            from django.contrib.auth import get_user_model
            username = request.POST.get("username")
            try:
                decoded_token = verify_supabase_token(id_token)
                uid = decoded_token.get('sub')
                email = decoded_token.get('email', '')
                
                User = get_user_model()
                if User.objects.filter(username=username).exists():
                    return render(request, "sign-up.html", {"error": "Username already taken."})
                
                # Ensure the Email isn't already linked
                if not User.objects.filter(email=email).exists():
                    user = User(username=username, email=email)
                    user.set_unusable_password()
                    user.save()
                    # Optionally store the Supabase UID (sub) in a profile field
                else:
                    return render(request, "sign-up.html", {"error": "Email already registered."})
                # Process referral code if provided
                referral_code_input = request.POST.get('referral_code', '').strip().upper()
                if referral_code_input:
                    from accounts.models import Referral
                    User2 = get_user_model()
                    referrer = User2.objects.filter(referral_code=referral_code_input).exclude(id=user.id).first()
                    if referrer and not user.referred_by:
                        user.referred_by = referrer
                        user.save(update_fields=['referred_by'])
                        Referral.objects.get_or_create(referrer=referrer, referred_user=user)
                    elif referral_code_input and not referrer:
                        return render(request, 'sign-up.html', {'error': 'Invalid referral code. Please check and try again.'})
            except Exception as e:
                return render(request, 'sign-up.html', {"error": f"Supabase Auth Error: {str(e)}"})
                
            return redirect('signin')

        # Fallback to legacy Django auth
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        confirm = request.POST.get("password_confirm")

        if password != confirm:
            return render(request, "sign-up.html", {
                "error": "Passwords do not match"
            })

        payload = {
            "username": username,
            "email": email,
            "password": password,
        }

        serializer = RegisterSerializer(data=payload)
        if serializer.is_valid():
            new_user = serializer.save()
            # Process referral code
            referral_code_input = request.POST.get('referral_code', '').strip().upper()
            if referral_code_input:
                from accounts.models import Referral
                from django.contrib.auth import get_user_model
                UserModel = get_user_model()
                referrer = UserModel.objects.filter(referral_code=referral_code_input).exclude(id=new_user.id).first()
                if referrer:
                    new_user.referred_by = referrer
                    new_user.save(update_fields=['referred_by'])
                    Referral.objects.get_or_create(referrer=referrer, referred_user=new_user)
                else:
                    return render(request, 'sign-up.html', {'error': 'Invalid referral code. Please check and try again.'})
            return redirect('signin')

        return render(request, 'sign-up.html', {
            'error': 'Registration failed. Please try again.'
        })

    return render(request, "sign-up.html")

@jwt_required
def dashboard(request):
    from streaming.models import FallbackVideo
    from official_site.models import SubscriptionPlan
    live_streams = []
    try:
        # We now rely SOLELY on the local Django database for active streams.
        # This is the "Consolidated Source of Truth" pattern.
        from streaming.models import LiveStream
        from django.db.models import Q
        unlocked = request.session.get('unlocked_streams', [])
        
        # Include public streams OR private streams the user has unlocked
        django_streams = LiveStream.objects.filter(
            Q(is_live=True, is_private=False) | Q(is_live=True, id__in=unlocked)
        ).order_by("-started_at")
        for st in django_streams:
            avatar_url = "https://ui-avatars.com/api/?name=" + st.streamer.username
            if hasattr(st.streamer, 'profile') and st.streamer.profile.avatar:
                avatar_url = st.streamer.profile.avatar.url
                
            live_streams.append({
                "streamid": str(st.id),
                "title": st.title or "My Live Stream",
                "category": st.category or "LIVE",
                "thumbnail_url": st.thumbnail.url if st.thumbnail else "https://ui-avatars.com/api/?name=Live",
                "streamer_username": st.streamer.username,
                "streamer_avatar": avatar_url,
                "viewers": st.viewer_count,
                "is_private": st.is_private
            })
    except Exception as e:
        print("Live Streams Fetch Error:", e)

    fallbacks = FallbackVideo.objects.filter(is_active=True)
    from official_site.models import TimeSubscriptionTier, CoinPackage, VirtualGift
    subscription_tiers = TimeSubscriptionTier.objects.filter(is_active=True).order_by('duration_hours')
    coin_packages = CoinPackage.objects.filter(is_active=True).order_by('coin_amount')
    virtual_gifts = VirtualGift.objects.filter(is_active=True).order_by('sort_order')

    coin_balance = 0
    following_list = []
    if request.user.is_authenticated:
        from payments.models import CoinWallet
        wallet, _ = CoinWallet.objects.get_or_create(user=request.user)
        coin_balance = wallet.balance
        
        from accounts.models import Follow
        # Fetch detailed info for the creators following
        following = Follow.objects.filter(follower=request.user).select_related('following', 'following__profile')
        for f in following:
            f_avatar = "https://ui-avatars.com/api/?name=" + f.following.username
            if hasattr(f.following, 'profile') and f.following.profile.avatar:
                f_avatar = f.following.profile.avatar.url
            
            following_list.append({
                "username": f.following.username,
                "avatar": f_avatar,
                "bio": getattr(f.following.profile, 'bio', "") if hasattr(f.following, 'profile') else "",
                "follower_count": Follow.objects.filter(following=f.following).count(),
                "following_count": Follow.objects.filter(follower=f.following).count(),
                # In the future, match with actual likes/gifts
                "likes_count": 0 
            })
    
    return render(request, "index.html", {
        "user": request.user,
        "live_streams": live_streams,
        "fallbacks": fallbacks,
        "subscription_tiers": subscription_tiers,
        "coin_packages": coin_packages,
        "virtual_gifts": virtual_gifts,
        "coin_balance": coin_balance,
        "following_list": following_list
    })


def logout_view(request):
    response = redirect("signin")
    response.delete_cookie("access")
    response.delete_cookie("refresh")
    return response

# Create your views here.
#navigation tabs start
@jwt_required
def userprofile(request):
    from accounts.models import Follow, StreamBooking
    
    following = Follow.objects.filter(follower=request.user).select_related('following', 'following__profile')
    followers = Follow.objects.filter(following=request.user).select_related('follower', 'follower__profile')
    booked_by = StreamBooking.objects.filter(streamer=request.user).select_related('user', 'user__profile')
    
    return render(request, 'form-wizard.html', {
        "user": request.user,
        "following_list": following,
        "followers_list": followers,
        "booked_by_list": booked_by,
        "following_count": following.count(),
        "followers_count": followers.count(),
        "booked_count": booked_by.count(),
    })

@jwt_required
@require_POST
def edit_profile(request):
    """
    Handle AJAX updates for X-style UserProfile fields.
    """
    profile = request.user.profile

    # Text fields
    if "display_name" in request.POST:
        profile.display_name = request.POST["display_name"]
    if "bio" in request.POST:
        profile.bio = request.POST["bio"]

    # Image fields
    if "avatar" in request.FILES:
        profile.avatar = request.FILES["avatar"]
    if "banner" in request.FILES:
        profile.banner_image = request.FILES["banner"]

    profile.save()

    return JsonResponse({
        "status": "success",
        "avatar_url": profile.avatar.url if profile.avatar else None,
        "banner_url": profile.banner_image.url if profile.banner_image else None,
        "display_name": profile.display_name,
        "bio": profile.bio
    })

@jwt_required
def userprivacy(request):
    privacy, _ = PrivacySettings.objects.get_or_create(user=request.user)

    if request.method == "POST":
        # Handle AJAX toggle updates
        field = request.POST.get("field")
        value = request.POST.get("value") == "true"

        if field in ["is_private_account", "allow_comments", "allow_duet", "allow_download"]:
            setattr(privacy, field, value)
            privacy.save()
            return JsonResponse({"status": "success", "message": f"{field} updated to {value}"})
        
        return JsonResponse({"status": "error", "message": "Invalid field"}, status=400)

    return render(request, 'user-privacy-setting.html', {
        "user": request.user,
        "privacy": privacy
    })

@jwt_required
def usersecurity(request):
    security, _ = SecuritySettings.objects.get_or_create(user=request.user)

    if request.method == "POST":
        # Handle AJAX toggle updates
        field = request.POST.get("field")
        value = request.POST.get("value") == "true"

        if field in ["two_factor_auth", "security_alerts"]:
            setattr(security, field, value)
            security.save()
            return JsonResponse({"status": "success", "message": f"{field} updated to {value}"})
        
        return JsonResponse({"status": "error", "message": "Invalid field"}, status=400)

    return render(request, 'user-security-setting.html', {
        "user": request.user,
        "security": security
    })


def recover_password(request):
    return render(request, 'recoverpw.html')

@jwt_required
def live(request):
    from official_site.models import SubscriptionPlan
    live_streams = []
    try:
        from streaming.models import LiveStream
        from accounts.models import Follow
        # Only show streams from followed creators
        following_ids = Follow.objects.filter(follower=request.user).values_list('following_id', flat=True)
        unlocked = request.session.get('unlocked_streams', [])
        from django.db.models import Q
        django_streams = LiveStream.objects.filter(
            Q(is_live=True, streamer_id__in=following_ids, is_private=False) | Q(is_live=True, id__in=unlocked)
        ).order_by("-started_at")
        
        for st in django_streams:
            avatar_url = "https://ui-avatars.com/api/?name=" + st.streamer.username
            if hasattr(st.streamer, 'profile') and st.streamer.profile.avatar:
                avatar_url = st.streamer.profile.avatar.url
                
            live_streams.append({
                "streamid": str(st.id),
                "title": st.title or "My Live Stream",
                "category": st.category or "LIVE",
                "thumbnail_url": st.thumbnail.url if st.thumbnail else "https://ui-avatars.com/api/?name=Live",
                "streamer_username": st.streamer.username,
                "streamer_avatar": avatar_url,
                "viewers": st.viewer_count,
                "is_private": st.is_private
            })
    except Exception as e:
        print("Live Page (Following) Fetch Error:", e)

    from official_site.models import TimeSubscriptionTier, CoinPackage, VirtualGift
    subscription_tiers = TimeSubscriptionTier.objects.filter(is_active=True).order_by('duration_hours')
    coin_packages = CoinPackage.objects.filter(is_active=True).order_by('coin_amount')
    virtual_gifts = VirtualGift.objects.filter(is_active=True).order_by('sort_order')

    coin_balance = 0
    following_list = []
    if request.user.is_authenticated:
        from payments.models import CoinWallet
        wallet, _ = CoinWallet.objects.get_or_create(user=request.user)
        coin_balance = wallet.balance

        from accounts.models import Follow
        # Fetch detailed info for the creators following
        following = Follow.objects.filter(follower=request.user).select_related('following', 'following__profile')
        for f in following:
            f_avatar = "https://ui-avatars.com/api/?name=" + f.following.username
            if hasattr(f.following, 'profile') and f.following.profile.avatar:
                f_avatar = f.following.profile.avatar.url

            following_list.append({
                "username": f.following.username,
                "avatar": f_avatar,
                "bio": getattr(f.following.profile, 'bio', "") if hasattr(f.following, 'profile') else "",
                "follower_count": Follow.objects.filter(following=f.following).count(),
                "following_count": Follow.objects.filter(follower=f.following).count(),
                # In the future, match with actual likes/gifts
                "likes_count": 0 
            })

    return render(request, 'live.html', {
        "user": request.user,
        "live_streams": live_streams,
        "subscription_tiers": subscription_tiers,
        "coin_packages": coin_packages,
        "virtual_gifts": virtual_gifts,
        "coin_balance": coin_balance,
        "following_list": following_list
    })

@jwt_required
def go_live(request):
    from django.conf import settings
    auth_token = None
    try:
        # In Supabase, we don't need to generate a custom token for the frontend 
        # as much as we just need the user to be authenticated in the browser. 
        # However, if using Supabase client in frontend, we pass the session token.
        auth_token = request.COOKIES.get("supabase-access-token") # Hypothetical cookie
    except Exception as e:
        print(f"Error retrieving auth session: {e}")

    return render(request, 'go_live.html', {
        "user": request.user,
        "auth_token": auth_token,
        "agora_app_id": settings.AGORA_APP_ID,
    })

@jwt_required
def chat(request):
    return render(request, 'chat.html', {
        "user": request.user
    })

@jwt_required
def conversation_detail(request, conversation_id):
    from chat.models import Conversation
    conversation = Conversation.objects.filter(id=conversation_id, members__user=request.user).first()
    if not conversation:
        return redirect('chat')
    
    # Get the other member for private chats
    other_user = None
    if conversation.type == conversation.Type.PRIVATE:
        member = conversation.members.exclude(user=request.user).first()
        if member:
            other_user = member.user

    return render(request, 'conversation_detail.html', {
        "user": request.user,
        "conversation": conversation,
        "other_user": other_user
    })

@jwt_required
def search(request):
    return render(request, 'search.html', {
        "user": request.user
    })

@jwt_required
def settings(request):
    return render(request, 'settings.html', {
        "user": request.user
    })

@jwt_required
def public_profile(request, username):
    from accounts.models import User, Follow
    from streaming.models import LiveStream
    
    target_user = User.objects.filter(username=username).first()
    if not target_user:
        return redirect('dashboard')
        
    following_count = Follow.objects.filter(follower=target_user).count()
    followers_count = Follow.objects.filter(following=target_user).count()
    
    # Check if current user is following target
    is_following = Follow.objects.filter(follower=request.user, following=target_user).exists()
    
    # Check if the user is currently live
    active_stream = LiveStream.objects.filter(streamer=target_user, is_live=True).first()
    
    # Fetch historical streams
    past_streams = LiveStream.objects.filter(streamer=target_user, is_live=False).order_by('-created_at')[:9]
    
    # Calculate Total Stream Minutes (sum of all sessions)
    from django.db.models import Sum
    from streaming.models import LiveViewSession
    total_stream_minutes = LiveViewSession.objects.filter(stream__streamer=target_user).aggregate(total=Sum('minutes_watched'))['total'] or 0
    
    # Get Coins (Wallet Balance)
    coins = 0
    if hasattr(target_user, 'wallet'):
        coins = target_user.wallet.total_balance
    
    # Check if this is the owner's view
    is_owner = (request.user == target_user)
    
    return render(request, 'public_profile.html', {
        "user": request.user,
        "target_user": target_user,
        "following_count": following_count,
        "followers_count": followers_count,
        "is_following": is_following,
        "active_stream": active_stream,
        "past_streams": past_streams,
        "is_owner": is_owner,
        "total_stream_minutes": total_stream_minutes,
        "coins": coins,
    })
@jwt_required
@require_POST
def toggle_follow(request, username):
    from accounts.models import User, Follow
    from django.http import JsonResponse
    
    target_user = User.objects.filter(username=username).first()
    if not target_user:
        return JsonResponse({"error": "User not found"}, status=404)
        
    if target_user == request.user:
        return JsonResponse({"error": "You cannot follow yourself"}, status=400)
        
    follow_obj = Follow.objects.filter(follower=request.user, following=target_user).first()
    
    if follow_obj:
        follow_obj.delete()
        is_following = False
    else:
        Follow.objects.create(follower=request.user, following=target_user)
        is_following = True
        
    followers_count = Follow.objects.filter(following=target_user).count()
    
    return JsonResponse({
        "is_following": is_following,
        "followers_count": followers_count
    })
    from accounts.models import UserWallet, PaymentAccount, EarningTransaction, PayoutLog
    
    # Ensure wallet exists
    wallet, created = UserWallet.objects.get_or_create(user=request.user)
    
    # Get payment accounts
    payment_accounts = PaymentAccount.objects.filter(user=request.user)
    
    # Get recent transactions
    earnings = EarningTransaction.objects.filter(user=request.user).order_by('-created_at')[:10]
    payouts = PayoutLog.objects.filter(user=request.user).order_by('-created_at')[:10]

    # Supabase migration: We no longer fetch legacy coin data from Firestore.
    # All coin/wallet data is now managed via Django UserWallet and CoinWallet models.
    user_data = {
        "username": request.user.username,
        "email": request.user.email,
        "coins": getattr(request.user, 'coin_wallet', None).balance if hasattr(request.user, 'coin_wallet') else 0
    }

    return render(request, 'wallet.html', {
        "user": request.user,
        "wallet": wallet,
        "payment_accounts": payment_accounts,
        "earnings": earnings,
        "payouts": payouts,
        "firebase_user": user_data
    })

@jwt_required
def platform_admin_overview(request):
    """
    Overview dashboard for Superadmins.
    """
    if not request.user.is_superuser:
        return redirect('dashboard')
        
    from accounts.models import UserProfile
    total_users = UserProfile.objects.count()
    from streaming.models import LiveStream
    active_streams = LiveStream.objects.filter(is_live=True).count()
    
    return render(request, 'platform_admin_overview.html', {
        'total_users': total_users,
        'active_streams': active_streams
    })

@jwt_required
def platform_admin_users(request):
    """
    User Management Dashboard.
    """
    if not request.user.is_superuser:
        return redirect('dashboard')
        
    from django.contrib.auth import get_user_model
    from django.db.models import Q
    from django.core.paginator import Paginator
    User = get_user_model()
    
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    
    users_qs = User.objects.all().order_by('-date_joined')
    
    if query:
        users_qs = users_qs.filter(
            Q(username__icontains=query) | 
            Q(email__icontains=query) |
            Q(userprofile__display_name__icontains=query)
        )
        
    if status_filter == 'active':
        users_qs = users_qs.filter(is_active=True)
    elif status_filter == 'banned' or status_filter == 'suspended':
        users_qs = users_qs.filter(is_active=False)
        
    paginator = Paginator(users_qs, 20) # 20 users per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'platform_admin_users.html', {
        'users': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages()
    })

@require_POST
@jwt_required
def platform_admin_toggle_user(request):
    """
    Ban or Unban a user from the Admin panel.
    """
    if not request.user.is_superuser:
        return redirect('dashboard')
        
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    user_id = request.POST.get('user_id')
    action = request.POST.get('action')
    
    if user_id and action:
        try:
            target_user = User.objects.get(id=user_id)
            if not target_user.is_superuser: # Prevent banning other superadmins
                if action == 'ban':
                    target_user.is_active = False
                elif action == 'unban':
                    target_user.is_active = True
                target_user.save()
        except User.DoesNotExist:
            pass
            
    return redirect('platform_admin_users')

@jwt_required
def platform_admin_wallets(request):
    """
    Wallets and Payouts admin interface.
    """
    if not request.user.is_superuser:
        return redirect('dashboard')
        
    from accounts.models import UserWallet, PaymentAccount, PayoutLog, AdminWalletConfig
    from django.db.models import Sum
    
    status_filter = request.GET.get('status', 'processing')
    
    # Payout Logs (Replacing manual Withdrawal Requests)
    payouts_qs = PayoutLog.objects.all().order_by('-created_at')
    if status_filter != 'all':
        payouts_qs = payouts_qs.filter(status=status_filter)
        
    # User Payment Accounts
    payment_accounts = PaymentAccount.objects.all().order_by('-created_at')
    
    # Wallet Config
    config = AdminWalletConfig.objects.first()
    
    # Financial Overview Aggregations
    total_pending_payouts = PayoutLog.objects.filter(status='processing').aggregate(Sum('amount'))['amount__sum'] or 0.00
    pending_count = PayoutLog.objects.filter(status='processing').count()
    
    from django.utils import timezone
    current_month = timezone.now().replace(day=1, hour=0, minute=0, second=0)
    total_processed = PayoutLog.objects.filter(
        status='paid', 
        processed_at__gte=current_month
    ).aggregate(Sum('amount'))['amount__sum'] or 0.00
    
    return render(request, 'platform_admin_wallets.html', {
        'payouts': payouts_qs,
        'payment_accounts': payment_accounts,
        'wallet_config': config,
        'total_pending': total_pending_payouts,
        'pending_count': pending_count,
        'total_processed': total_processed
    })

@require_POST
@jwt_required
def platform_admin_process_payout(request):
    """
    Mark a payout as Paid or Failed.
    """
    if not request.user.is_superuser:
        return redirect('dashboard')
        
    from accounts.models import PayoutLog
    from django.utils import timezone
    
    payout_id = request.POST.get('payout_id')
    action = request.POST.get('action')
    
    if payout_id and action:
        try:
            payout = PayoutLog.objects.get(id=payout_id)
            if action == 'mark_paid':
                payout.status = 'paid'
                payout.processed_at = timezone.now()
            elif action == 'mark_failed':
                payout.status = 'failed'
                # Revert funds? Usually yes if it failed.
                from accounts.models import UserWallet
                wallet = UserWallet.objects.get(user=payout.user)
                wallet.withdrawable_balance += payout.amount
                wallet.save()
            payout.save()
        except PayoutLog.DoesNotExist:
            pass
            
    return redirect('platform_admin_wallets')

@require_POST
@jwt_required
def platform_admin_process_withdrawal(request):
    """
    Approve, Reject, or Mark Paid a withdrawal request.
    """
    if not request.user.is_superuser:
        return redirect('dashboard')
        
    from accounts.models import WithdrawalRequest
    from django.utils import timezone
    
    request_id = request.POST.get('request_id')
    action = request.POST.get('action')
    
    if request_id and action:
        try:
            req = WithdrawalRequest.objects.get(id=request_id)
            if action == 'approve' and req.status == 'pending':
                req.status = 'approved'
            elif action == 'reject' and req.status == 'pending':
                req.status = 'rejected'
            elif action == 'mark_paid' and req.status == 'approved':
                req.status = 'paid'
                req.processed_at = timezone.now()
            req.save()
        except WithdrawalRequest.DoesNotExist:
            pass
            
    return redirect('platform_admin_wallets')

@require_POST
@jwt_required
def platform_admin_verify_account(request):
    """
    Verify or De-verify a user's payment account for withdrawals.
    """
    if not request.user.is_superuser:
        return redirect('dashboard')
        
    from accounts.models import PaymentAccount
    from django.urls import reverse
    
    account_id = request.POST.get('account_id')
    
    if account_id:
        try:
            acc = PaymentAccount.objects.get(id=account_id)
            acc.is_verified = not acc.is_verified # Toggle
            acc.save()
        except PaymentAccount.DoesNotExist:
            pass
            
    return redirect(f"{reverse('platform_admin_wallets')}#accounts")

@jwt_required
def platform_admin_subscriptions(request):
    """
    Manage Time Subscriptions, Coin Packages, and Virtual Gifts.
    """
    if not request.user.is_superuser:
        return redirect('dashboard')
        
    from official_site.models import TimeSubscriptionTier, CoinPackage, VirtualGift
    from django.urls import reverse
    
    tiers = TimeSubscriptionTier.objects.all().order_by('duration_hours')
    
    # If no tiers exist, populate defaults
    if not tiers.exists():
        TimeSubscriptionTier.objects.create(duration_hours=6, price=4.99)
        TimeSubscriptionTier.objects.create(duration_hours=12, price=8.99)
        TimeSubscriptionTier.objects.create(duration_hours=24, price=14.99)
        TimeSubscriptionTier.objects.create(duration_hours=48, price=24.99)
        tiers = TimeSubscriptionTier.objects.all().order_by('duration_hours')
        
    coin_packages = CoinPackage.objects.all().order_by('coin_amount')
    if not coin_packages.exists():
        CoinPackage.objects.create(coin_amount=100, price=1.00)
        CoinPackage.objects.create(coin_amount=500, price=4.50, bonus_coins=50)
        CoinPackage.objects.create(coin_amount=1000, price=8.00, bonus_coins=200)
        coin_packages = CoinPackage.objects.all().order_by('coin_amount')
        
    virtual_gifts = VirtualGift.objects.all()
    if not virtual_gifts.exists():
        VirtualGift.objects.create(name='Rose', coin_cost=10, css_icon_class='local_florist', sort_order=1)
        VirtualGift.objects.create(name='Heart', coin_cost=50, css_icon_class='favorite', sort_order=2)
        VirtualGift.objects.create(name='Diamond', coin_cost=500, css_icon_class='diamond', sort_order=3)
        virtual_gifts = VirtualGift.objects.all()
        
    return render(request, 'platform_admin_subscriptions.html', {
        'tiers': tiers,
        'coin_packages': coin_packages,
        'virtual_gifts': virtual_gifts,
        'monthly_revenue': "2,450.00", # Mocked for now
        'active_subs_count': 142
    })

@require_POST
@jwt_required
def platform_admin_update_subscription(request):
    if not request.user.is_superuser:
        return redirect('dashboard')
        
    from official_site.models import TimeSubscriptionTier
    tier_id = request.POST.get('tier_id')
    price = request.POST.get('price')
    discount = request.POST.get('discount')
    is_active = request.POST.get('is_active') == 'on'
    
    if tier_id:
        try:
            tier = TimeSubscriptionTier.objects.get(id=tier_id)
            tier.price = price
            tier.discount_percentage = discount
            tier.is_active = is_active
            tier.save()
        except TimeSubscriptionTier.DoesNotExist:
            pass
            
    return redirect('platform_admin_subscriptions')

@require_POST
@jwt_required
def platform_admin_update_coin_package(request):
    if not request.user.is_superuser:
        return redirect('dashboard')
        
    from official_site.models import CoinPackage
    pkg_id = request.POST.get('pkg_id')
    price = request.POST.get('price')
    bonus = request.POST.get('bonus')
    is_active = request.POST.get('is_active') == 'on'
    
    if pkg_id:
        try:
            pkg = CoinPackage.objects.get(id=pkg_id)
            pkg.price = price
            pkg.bonus_coins = bonus
            pkg.is_active = is_active
            pkg.save()
        except CoinPackage.DoesNotExist:
            pass
            
    return redirect(f"{reverse('platform_admin_subscriptions')}#coins")

@require_POST
@jwt_required
def platform_admin_update_virtual_gift(request):
    if not request.user.is_superuser:
        return redirect('dashboard')
        
    from official_site.models import VirtualGift
    gift_id = request.POST.get('gift_id')
    cost = request.POST.get('cost')
    is_active = request.POST.get('is_active') == 'on'
    
    if gift_id:
        try:
            gift = VirtualGift.objects.get(id=gift_id)
            gift.coin_cost = cost
            gift.is_active = is_active
            gift.save()
        except VirtualGift.DoesNotExist:
            pass
            
    return redirect(f"{reverse('platform_admin_subscriptions')}#gifts")

def platform_admin_login(request):
    """
    Dedicated login view for Platform Administrators.
    """
    # If already logged in and is superuser, redirect straight to dashboard
    raw_token = request.COOKIES.get("access")
    if raw_token:
        from rest_framework_simplejwt.authentication import JWTAuthentication
        jwt_auth = JWTAuthentication()
        try:
            validated_token = jwt_auth.get_validated_token(raw_token)
            user = jwt_auth.get_user(validated_token)
            if user.is_superuser:
                return redirect('platform_admin_overview')
        except Exception:
            pass
            
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")
        
        user = authenticate(email=email, password=password)
        
        if not user or not user.is_active:
            return render(request, "platform_admin_login.html", {
                "error": "Invalid credentials"
            })
            
        if not user.is_superuser:
            return render(request, "platform_admin_login.html", {
                "error": "Access Denied: You are not a platform administrator."
            })
            
        from accounts.tokens import get_tokens_for_user
        tokens = get_tokens_for_user(user)
        response = redirect("platform_admin_overview")
        response.set_cookie("access", tokens["access"], httponly=True, samesite="Lax")
        response.set_cookie("refresh", tokens["refresh"], httponly=True, samesite="Lax")
        return response
        
    return render(request, "platform_admin_login.html")

@jwt_required
@require_POST
def add_payment_account(request):
    from accounts.models import PaymentAccount
    
    bank_name = request.POST.get('bank_name')
    account_name = request.POST.get('account_name')
    account_number = request.POST.get('account_number')
    
    if not all([bank_name, account_name, account_number]):
        return JsonResponse({'status': 'error', 'message': 'All fields are required.'}, status=400)
        
    PaymentAccount.objects.create(
        user=request.user,
        account_type='bank',
        bank_name=bank_name,
        account_name=account_name,
        account_number=account_number
    )
    
    return JsonResponse({'status': 'success', 'message': 'Account added and pending verification.'})

@jwt_required
@require_POST
def withdraw_funds(request):
    from accounts.models import UserWallet, PaymentAccount, PayoutLog
    from django.shortcuts import get_object_or_404
    
    wallet = get_object_or_404(UserWallet, user=request.user)
    
    if wallet.is_frozen:
        return JsonResponse({'status': 'error', 'message': 'Your wallet is frozen. Please contact support.'}, status=403)
        
    # Check if they have a verified payment account
    account = PaymentAccount.objects.filter(user=request.user, is_verified=True).first()
    if not account:
        return JsonResponse({'status': 'error', 'message': 'No verified bank account found.'}, status=400)
        
    amount = wallet.withdrawable_balance
    if amount < 50:
        return JsonResponse({'status': 'error', 'message': 'Minimum withdrawal is $50.00'}, status=400)
        
    # Deduct balance
    wallet.withdrawable_balance -= amount
    wallet.save()
    
    payout = PayoutLog.objects.create(
        user=request.user,
        payment_account=account,
        amount=amount,
        status='processing'
    )
    
    return JsonResponse({'status': 'success', 'message': 'Withdrawal initiated.'})

@jwt_required
def private_stream_access(request, private_token):
    from streaming.models import LiveStream, InvitedUser, JoinRequest
    from django.shortcuts import get_object_or_404
    
    stream = get_object_or_404(LiveStream, private_token=private_token)
    
    # If the stream is public, redirect to the live feed
    if not stream.is_private:
        return redirect('live')
        
    # If user is the host, redirect to live feed where they can view it.
    if stream.streamer == request.user:
        return redirect('live')

    # Check if user is explicitly invited (Bypass)
    is_invited = InvitedUser.objects.filter(stream=stream, user=request.user).exists()
    
    unlocked_streams = request.session.get('unlocked_streams', [])
    if str(stream.id) in unlocked_streams or is_invited:
        if str(stream.id) not in unlocked_streams:
            unlocked_streams.append(str(stream.id))
            request.session['unlocked_streams'] = unlocked_streams
        return redirect('live')

    # Handle Password submission / logic
    if request.method == "POST":
        action = request.POST.get("action")
        
        if action == "submit_password":
            password_attempt = request.POST.get("password", "")
            if stream.password and stream.password == password_attempt:
                if not stream.requires_approval:
                    unlocked_streams.append(str(stream.id))
                    request.session['unlocked_streams'] = unlocked_streams
                    return redirect('live')
                else:
                    # Password correct, now requires approval. Add to JoinRequest
                    JoinRequest.objects.get_or_create(stream=stream, viewer=request.user)
                    return render(request, "private_stream_auth.html", {
                        "stream": stream,
                        "status": "pending_approval"
                    })
            else:
                return render(request, "private_stream_auth.html", {
                    "stream": stream,
                    "error": "Incorrect password. Please try again.",
                    "status": "password_required"
                })

    # Render appropriate starting state
    status_state = "password_required" if stream.password else "pending_approval"
    
    if status_state == "pending_approval":
        # If no password but needs approval, auto-submit request
        req, created = JoinRequest.objects.get_or_create(stream=stream, viewer=request.user)
        if req.status == 'approved':
            unlocked_streams.append(str(stream.id))
            request.session['unlocked_streams'] = unlocked_streams
            return redirect('live')
        elif req.status == 'rejected':
            status_state = "rejected"
            
    return render(request, "private_stream_auth.html", {
        "stream": stream,
        "status": status_state
    })

@jwt_required
def private_stream_action(request, token):
    from streaming.models import LiveStream, JoinRequest, InvitedUser
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    stream = LiveStream.objects.filter(private_token=token, streamer=request.user).first()
    if not stream:
        return JsonResponse({"error": "Unauthorized or stream not found"}, status=403)
        
    action = request.POST.get("action")
    
    if action == "approve":
        viewer_id = request.POST.get("viewer_id")
        req = JoinRequest.objects.filter(stream=stream, viewer_id=viewer_id, status="pending").first()
        if req:
            req.status = "approved"
            req.save()
            return JsonResponse({"status": "success", "message": "Request approved."})
            
    elif action == "reject":
        viewer_id = request.POST.get("viewer_id")
        req = JoinRequest.objects.filter(stream=stream, viewer_id=viewer_id, status="pending").first()
        if req:
            req.status = "rejected"
            req.save()
            return JsonResponse({"status": "success", "message": "Request rejected."})
            
    elif action == "invite":
        username = request.POST.get("username")
        viewer = User.objects.filter(username=username).first()
        if viewer:
            InvitedUser.objects.get_or_create(stream=stream, user=viewer, invited_by=request.user)
            return JsonResponse({"status": "success", "message": f"{username} invited."})
            
    elif action == "get_requests":
        pending = JoinRequest.objects.filter(stream=stream, status="pending")
        data = [{"id": req.viewer.id, "username": req.viewer.username} for req in pending]
        return JsonResponse({"status": "success", "requests": data})

    return JsonResponse({"error": "Invalid action"}, status=400)

@jwt_required
def platform_admin_streams(request):
    """
    Stream Monitoring Dashboard for Superadmin.
    """
    if not request.user.is_superuser:
        return redirect('dashboard')
        
    from streaming.models import LiveStream
    from django.db.models import Q
    
    query = request.GET.get('q', '')
    
    # Bypass all privacy checks - admin sees everything that is currently LIVE
    streams_qs = LiveStream.objects.filter(is_live=True).order_by('-started_at')
    
    if query:
        streams_qs = streams_qs.filter(
            Q(streamer__username__icontains=query) | 
            Q(title__icontains=query) |
            Q(category__icontains=query)
        )
        
    return render(request, 'platform_admin_streams.html', {
        'streams': streams_qs,
        'query': query
    })

@jwt_required
@require_POST
def platform_admin_end_stream(request):
    """
    API for Admins to forcefully terminate a live stream.
    """
    if not request.user.is_superuser:
        return JsonResponse({"error": "Forbidden"}, status=403)
        
    stream_id = request.POST.get('stream_id')
    if not stream_id:
        return JsonResponse({"error": "No stream ID provided"}, status=400)
        
    from streaming.models import LiveStream, LiveViewSession
    from django.utils import timezone
    from decimal import Decimal
    import random
    from django.db import transaction
    from django.db.models import F
    
    with transaction.atomic():
        try:
            stream = LiveStream.objects.select_for_update().get(id=stream_id, is_live=True)
        except LiveStream.DoesNotExist:
            return JsonResponse({"error": "Stream not active or not found"}, status=404)
            
        stream.is_live = False
        stream.ended_at = timezone.now()
        stream.save(update_fields=["is_live", "ended_at"])
        
        # Settle active view sessions just like the normal End process so data isn't corrupt
        active_sessions = LiveViewSession.objects.select_for_update().filter(stream=stream, is_active=True)
        total_earnings = Decimal("0.00")
        
        for session in active_sessions:
            session.force_end(reason="admin_terminated")
            minutes = session.active_seconds // 60
            session.minutes_watched = minutes
            
            earnings = Decimal("0.00")
            if minutes >= 2: # MIN_PAYABLE_MINUTES
                earnings = Decimal(minutes) * Decimal(str(random.uniform(0.05, 0.20)))
                
            session.earnings_generated = earnings
            session.save(update_fields=["is_active", "ended_at", "minutes_watched", "earnings_generated"])
            total_earnings += earnings
            
        stream.total_earnings = F("total_earnings") + total_earnings
        stream.save(update_fields=["total_earnings"])
        
    return JsonResponse({"status": "success", "message": "Stream forcefully terminated."})


# ==========================================
# REFERRAL CODE VIEWS
# ==========================================

@jwt_required
@require_POST
def generate_referral_code(request):
    import secrets, string
    user = request.user
    # Generate unique 8-char uppercase alphanumeric code
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(10):  # try up to 10 times for uniqueness
        code = ''.join(secrets.choice(alphabet) for _ in range(8))
        from accounts.models import User as UserModel
        if not UserModel.objects.filter(referral_code=code).exists():
            user.referral_code = code
            user.save(update_fields=['referral_code'])
            return JsonResponse({"referral_code": code})
    return JsonResponse({"error": "Could not generate unique code. Try again."}, status=500)


# ==========================================
# WALLET PAGE VIEWS
# ==========================================

@jwt_required
def wallet(request):
    from accounts.models import UserWallet, WalletTransaction
    from payments.models import CoinWallet

    wallet_obj, _ = UserWallet.objects.get_or_create(user=request.user)
    coin_wallet, _ = CoinWallet.objects.get_or_create(user=request.user)
    transactions = WalletTransaction.objects.filter(user=request.user)[:50]

    return render(request, 'wallet.html', {
        'user': request.user,
        'wallet': wallet_obj,
        'coin_balance': coin_wallet.balance,
        'transactions': transactions,
    })


@jwt_required
def wallet_transactions(request):
    from accounts.models import WalletTransaction
    from django.core.paginator import Paginator

    page = int(request.GET.get('page', 1))
    qs = WalletTransaction.objects.filter(user=request.user)
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(page)

    data = [
        {
            'type': t.type,
            'amount_usd': str(t.amount_usd),
            'description': t.description,
            'created_at': t.created_at.strftime('%b %d, %Y %H:%M'),
        }
        for t in page_obj
    ]
    return JsonResponse({'transactions': data, 'has_next': page_obj.has_next()})


# ==========================================
# ADMIN: REFERRAL MANAGEMENT
# ==========================================

@jwt_required
def platform_admin_referrals(request):
    if not request.user.is_superuser:
        return redirect('dashboard')

    from accounts.models import Referral, ReferralSettings
    from django.core.paginator import Paginator

    query = request.GET.get('q', '')
    referrals_qs = Referral.objects.select_related('referrer', 'referred_user').order_by('-created_at')

    if query:
        from django.db.models import Q
        referrals_qs = referrals_qs.filter(
            Q(referrer__username__icontains=query) | Q(referred_user__username__icontains=query)
        )

    paginator = Paginator(referrals_qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    settings_obj = ReferralSettings.get_settings()

    return render(request, 'platform_admin_referrals.html', {
        'page_obj': page_obj,
        'query': query,
        'settings': settings_obj,
    })


@jwt_required
def platform_admin_referral_settings(request):
    if not request.user.is_superuser:
        return redirect('dashboard')

    from accounts.models import ReferralSettings
    settings_obj = ReferralSettings.get_settings()

    if request.method == 'POST':
        try:
            settings_obj.reward_new_user_usd = request.POST.get('reward_new_user_usd', settings_obj.reward_new_user_usd)
            settings_obj.reward_referrer_usd = request.POST.get('reward_referrer_usd', settings_obj.reward_referrer_usd)
            settings_obj.is_active = request.POST.get('is_active') == 'on'
            settings_obj.save()
            return JsonResponse({'status': 'success', 'message': 'Referral settings updated.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    return render(request, 'platform_admin_referrals.html', {'settings': settings_obj})
