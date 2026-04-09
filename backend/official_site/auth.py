from functools import wraps
from django.shortcuts import redirect
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError



def jwt_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        raw_token = request.COOKIES.get("access")
        
        def redirect_target():
            if request.path.startswith('/platform-admin/'):
                return redirect('platform_admin_login')
            return redirect('signin')

        if not raw_token:
            return redirect_target()

        jwt_auth = JWTAuthentication()

        try:
            validated_token = jwt_auth.get_validated_token(raw_token)
            user = jwt_auth.get_user(validated_token)

            # 🔒 Enforce your domain rules
            from django.utils import timezone
            if getattr(user, "is_banned", False):
                return redirect_target()
            if getattr(user, "suspended_until", None) and user.suspended_until > timezone.now():
                return redirect_target()

        except AuthenticationFailed:
            return redirect_target()
        except Exception:
            return redirect_target()


        except TokenError:
            response = redirect_target()
            response.delete_cookie("access")
            response.delete_cookie("refresh")
            return response


        request.user = user
        return view_func(request, *args, **kwargs)

    return wrapper
