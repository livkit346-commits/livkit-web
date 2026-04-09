import jwt
import os
from supabase import create_client, Client
from django.conf import settings

# Initialize Supabase Client
supabase_url = os.environ.get("SUPABASE_URL", "https://your-project.supabase.co")
supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "your-service-role-key")
supabase: Client = create_client(supabase_url, supabase_key)

def verify_supabase_token(token: str):
    """
    Verifies a Supabase JWT token using the project's JWT secret.
    Returns the decoded payload if valid, else raises an exception.
    """
    jwt_secret = os.environ.get("SUPABASE_JWT_SECRET", "")
    if not jwt_secret:
        raise ValueError("SUPABASE_JWT_SECRET not set in environment.")
    
    try:
        # Supabase uses HS256 by default for its JWTs
        payload = jwt.decode(
            token, 
            jwt_secret, 
            algorithms=["HS256"], 
            audience="authenticated"
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired.")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token.")
    except Exception as e:
        raise ValueError(f"Token verification failed: {str(e)}")

def get_supabase_user(token: str):
    """
    Uses the Supabase client to get the user object from a token.
    This is an alternative to local JWT verification if you want to hit the Supabase API.
    """
    try:
        user = supabase.auth.get_user(token)
        return user
    except Exception as e:
        print(f"Supabase Get User Error: {e}")
        return None
