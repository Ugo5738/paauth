from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from supabase._async.client import AsyncClient
from gotrue.errors import AuthApiError as SupabaseAPIError
import logging

from auth_service.supabase_client import get_supabase_client
from auth_service.schemas.user_schemas import SupabaseUser # Assuming SupabaseUser schema is appropriate

logger = logging.getLogger(__name__)

# The tokenUrl should ideally point to your token-issuing endpoint (e.g., /auth/users/login)
# For dependency usage to extract Bearer token, it's mainly for documentation and OpenAPI spec.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/users/login")

async def get_current_supabase_user(
    token: str = Depends(oauth2_scheme),
    supabase: AsyncClient = Depends(get_supabase_client)
) -> SupabaseUser:
    """
    Dependency to get the current authenticated Supabase user from a JWT.
    Validates the token and returns the user object or raises HTTPException.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        logger.debug(f"Attempting to get user with token: {token[:20]}...") # Log truncated token
        user_response = await supabase.auth.get_user(jwt=token)
        
        if not user_response or not user_response.user:
            logger.warning(f"Token validation failed or no user returned for token: {token[:20]}...")
            raise credentials_exception
        
        # Map the gotrue.models.User to our Pydantic SupabaseUser schema
        # This ensures consistency in how user data is structured within our app.
        # Note: Supabase-py's user_response.user is already a gotrue.models.User object.
        # We need to ensure all fields match our Pydantic model or handle discrepancies.
        # For simplicity, assuming direct attribute compatibility for now.
        # In a real scenario, you might need more careful mapping if structures differ significantly.
        current_user = SupabaseUser(
            id=user_response.user.id,
            aud=user_response.user.aud or "", # Ensure aud is not None
            role=user_response.user.role,
            email=user_response.user.email,
            phone=user_response.user.phone,
            email_confirmed_at=user_response.user.email_confirmed_at,
            phone_confirmed_at=user_response.user.phone_confirmed_at,
            confirmed_at=getattr(user_response.user, 'confirmed_at', user_response.user.email_confirmed_at or user_response.user.phone_confirmed_at),
            last_sign_in_at=user_response.user.last_sign_in_at,
            app_metadata=user_response.user.app_metadata or {},
            user_metadata=user_response.user.user_metadata or {},
            identities=user_response.user.identities or [],
            created_at=user_response.user.created_at,
            updated_at=user_response.user.updated_at
        )
        logger.info(f"Successfully validated token for user: {current_user.email}")
        return current_user
    except SupabaseAPIError as e:
        logger.warning(f"Supabase API error during token validation: {e.message} (Status: {e.status})")
        if e.message == "Token expired" or e.status == 401:
             # More specific error for expired or explicitly invalid token
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid or expired token: {e.message}",
                headers={"WWW-Authenticate": "Bearer"},
            )
        raise credentials_exception # Fallback for other Supabase API errors
    except Exception as e:
        logger.error(f"Unexpected error during token validation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while validating authentication token."
        )


from auth_service.config import settings as app_settings_instance # Import the instance
from auth_service.config import Settings as AppSettingsType # Import the type for type hinting

def get_app_settings() -> AppSettingsType:
    """
    Dependency to get the application settings instance.
    """
    return app_settings_instance

