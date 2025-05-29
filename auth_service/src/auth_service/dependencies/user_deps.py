from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from supabase._async.client import AsyncClient
from gotrue.errors import AuthApiError
from gotrue.types import User as SupabaseUser

from auth_service.supabase_client import get_supabase_client # Assuming this provides the async client

# This scheme can be updated if we use a different path for token acquisition later
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/users/login", auto_error=False) 

async def get_current_supabase_user(
    token: str = Depends(oauth2_scheme), 
    supabase: AsyncClient = Depends(get_supabase_client)
) -> SupabaseUser:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        # Validate the token and get the user
        user_response = await supabase.auth.get_user(jwt=token)
        if user_response and user_response.user:
            return user_response.user
        else:
            # This case should ideally not be reached if get_user throws AuthApiError for invalid tokens
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except AuthApiError as e:
        # Handle specific Supabase errors, e.g., token expired, invalid token
        error_detail = "Invalid authentication credentials"
        if "invalid JWT" in str(e).lower() or "token is expired" in str(e).lower():
            error_detail = "Invalid or expired token"
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_detail,
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        # Catch any other unexpected errors during token validation
        # Log this error for debugging
        # logger.error(f"Unexpected error during token validation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not validate credentials",
        )
