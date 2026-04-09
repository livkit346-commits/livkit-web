from django.urls import path

from . import views

urlpatterns = [
    # Cleaned up old website routes
    path('',views.dashboard, name='dashboard'),
    path('userprofile',views.userprofile, name='userprofile'),
    path('edit_profile', views.edit_profile, name='edit_profile'),
    path('userprivacy',views.userprivacy, name='userprivacy'),
    path('usersecurity',views.usersecurity, name='usersecurity'),
    path('sign_in',views.sign_in, name='signin'),
    path('sign_up',views.sign_up, name='signup'),
    path('recover-password',views.recover_password, name='recover-password'),
    
    path('live', views.live, name='live'),
    path('live/private/<str:private_token>/', views.private_stream_access, name='private_stream_access'),
    path('api/stream/<str:token>/action/', views.private_stream_action, name='private_stream_action'),
    path('go_live', views.go_live, name='go_live'),
    path('chat', views.chat, name='chat'),
    path('chat/<uuid:conversation_id>/', views.conversation_detail, name='conversation_detail'),
    path('search', views.search, name='home_search'),
    path('settings', views.settings, name='settings'),
    path('profile/<str:username>/', views.public_profile, name='public_profile'),
    path('wallet', views.wallet, name='wallet'),
    path('api/referral/generate/', views.generate_referral_code, name='generate_referral_code'),
    path('api/wallet/transactions/', views.wallet_transactions, name='wallet_transactions'),
    # path('wallet', views.wallet, name='wallet'),

    
    # Platform Admin Routes
    path('platform-admin/login/', views.platform_admin_login, name='platform_admin_login'),
    path('platform-admin/', views.platform_admin_overview, name='platform_admin_overview'),
    path('platform-admin/users/', views.platform_admin_users, name='platform_admin_users'),
    path('platform-admin/users/toggle/', views.platform_admin_toggle_user, name='platform_admin_toggle_user'),
    path('platform-admin/subscriptions/', views.platform_admin_subscriptions, name='platform_admin_subscriptions'),
    path('platform-admin/subscriptions/update/', views.platform_admin_update_subscription, name='platform_admin_update_subscription'),
    path('platform-admin/subscriptions/update-coin/', views.platform_admin_update_coin_package, name='platform_admin_update_coin_package'),
    path('platform-admin/subscriptions/update-gift/', views.platform_admin_update_virtual_gift, name='platform_admin_update_virtual_gift'),
    
    # Stream Monitoring
    path('platform-admin/streams/', views.platform_admin_streams, name='platform_admin_streams'),
    path('platform-admin/streams/force-end/', views.platform_admin_end_stream, name='platform_admin_end_stream'),
    
    path('platform-admin/wallets/', views.platform_admin_wallets, name='platform_admin_wallets'),
    path('platform-admin/wallets/process/', views.platform_admin_process_payout, name='platform_admin_process_payout'),
    path('platform-admin/wallets/verify/', views.platform_admin_verify_account, name='platform_admin_verify_account'),
    path('platform-admin/referrals/', views.platform_admin_referrals, name='platform_admin_referrals'),
    path('platform-admin/referrals/settings/', views.platform_admin_referral_settings, name='platform_admin_referral_settings'),
    
    path('api/wallet/add-account', views.add_payment_account, name='add_payment_account'),
    path('api/wallet/withdraw', views.withdraw_funds, name='withdraw_funds'),
    
    path('logout', views.logout_view, name='logout'),
    path('api/accounts/toggle-follow/<str:username>/', views.toggle_follow, name='toggle_follow'),
    
]