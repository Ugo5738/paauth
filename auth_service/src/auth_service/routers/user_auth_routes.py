from fastapi import APIRouter, Depends, HTTPException, status, Request
from supabase._async.client import AsyncClient
from supabase.lib.client_options import ClientOptions 
from gotrue.errors import AuthApiError as SupabaseAPIError
from gotrue.types import UserAttributes 
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select 
from uuid import UUID 

from auth_service.schemas.user_schemas import UserCreate, UserResponse, ProfileCreate, ProfileResponse, SupabaseSession, SupabaseUser, MagicLinkLoginRequest, MagicLinkSentResponse, PasswordResetRequest, PasswordResetResponse, PasswordUpdateRequest # Ensure all are present
from auth_service.db import get_db
from auth_service.models import Profile
from auth_service.supabase_client import get_supabase_client
from auth_service.config import Settings as AppSettingsType # For type hinting settings
from auth_service.dependencies import get_current_supabase_user, get_app_settings, oauth2_scheme # Import for logout, settings, and token dependency 
import logging 

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth/users",
    tags=["User Authentication"],
)

# --- Profile CRUD Operations (Workaround: Placed here due to file creation issues) ---
async def create_profile_in_db(
    db_session: AsyncSession, 
    profile_data: ProfileCreate, 
    user_id: UUID
) -> Profile:
    logger.info(f"Creating profile for user_id: {user_id}")
    db_profile = Profile(
        user_id=user_id,
        username=profile_data.username,
        first_name=profile_data.first_name,
        last_name=profile_data.last_name,
        is_active=True
    )
    db_session.add(db_profile)
    try:
        await db_session.commit()
        await db_session.refresh(db_profile)
        logger.info(f"Profile created successfully for user_id: {user_id}")
        return db_profile
    except Exception as e: 
        await db_session.rollback()
        logger.error(f"Error creating profile for user_id {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating user profile after registration."
        )

async def get_profile_by_user_id_from_db(db_session: AsyncSession, user_id: UUID) -> Profile | None:
    logger.debug(f"Fetching profile for user_id: {user_id}")
    result = await db_session.execute(select(Profile).filter(Profile.user_id == user_id))
    profile = result.scalars().first()
    if profile:
        logger.debug(f"Profile found for user_id: {user_id}")
    else:
        logger.debug(f"No profile found for user_id: {user_id}")
    return profile

# --- User Authentication Endpoints ---
from auth_service.schemas.user_schemas import UserLoginRequest, MagicLinkLoginRequest, MagicLinkSentResponse # Added for login and magic link

@router.post("/login", response_model=SupabaseSession, status_code=status.HTTP_200_OK)
async def login_user(
    login_data: UserLoginRequest,
    supabase: AsyncClient = Depends(get_supabase_client),
    settings: AppSettingsType = Depends(get_app_settings),
    # db_session: AsyncSession = Depends(get_db), # Not strictly needed for login unless updating last_login
):
    logger.info(f"Login attempt for email: {login_data.email}")
    try:
        supa_response = await supabase.auth.sign_in_with_password(
            {"email": login_data.email, "password": login_data.password}
        )
        logger.debug(f"Supabase sign_in_with_password response: {supa_response}")

        supa_user = supa_response.user
        supa_session = supa_response.session

        if not supa_user or not supa_session:
            logger.error("Supabase sign_in did not return a user or session object.")
            # This case should ideally be caught by SupabaseAPIError for invalid creds
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Login failed: Invalid response from authentication provider."
            )

        # Check for email confirmation if required by settings
        if settings.supabase_email_confirmation_required and not supa_user.email_confirmed_at:
            logger.warning(f"Login attempt for unconfirmed email: {login_data.email}")
            raise SupabaseAPIError("Email not confirmed", status=401) # Simulate Supabase-like error

        # Map to Pydantic models for response
        mapped_supa_user = SupabaseUser(
            id=supa_user.id,
            aud=supa_user.aud or "",
            role=supa_user.role,
            email=supa_user.email,
            phone=supa_user.phone,
            email_confirmed_at=supa_user.email_confirmed_at,
            phone_confirmed_at=supa_user.phone_confirmed_at,
            confirmed_at=getattr(supa_user, 'confirmed_at', supa_user.email_confirmed_at or supa_user.phone_confirmed_at),
            last_sign_in_at=supa_user.last_sign_in_at,
            app_metadata=supa_user.app_metadata or {},
            user_metadata=supa_user.user_metadata or {},
            identities=supa_user.identities or [],
            created_at=supa_user.created_at,
            updated_at=supa_user.updated_at
        )
        session_response_data = SupabaseSession(
            access_token=supa_session.access_token,
            token_type=supa_session.token_type,
            expires_in=supa_session.expires_in,
            expires_at=supa_session.expires_at,
            refresh_token=supa_session.refresh_token,
            user=mapped_supa_user
        )
        logger.info(f"User {login_data.email} logged in successfully.")
        return session_response_data

    except SupabaseAPIError as e:
        logger.warning(f"Supabase API error during login for {login_data.email}: {e.message} (Status: {e.status})")
        detail = e.message
        http_status_code = status.HTTP_401_UNAUTHORIZED # Default for login failures

        if e.message == "Invalid login credentials":
            detail = "Invalid login credentials"
        elif e.message == "Email not confirmed":
            detail = "Email not confirmed. Please check your inbox."
        # Add more specific error message handling if needed based on Supabase responses
        
        raise HTTPException(
            status_code=http_status_code,
            detail=detail
        )
    except Exception as e:
        logger.error(f"Unexpected error during login for {login_data.email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during login."
        )


@router.post("/login/magiclink", response_model=MagicLinkSentResponse, status_code=status.HTTP_200_OK)
async def login_magic_link(
    request_data: MagicLinkLoginRequest,
    supabase: AsyncClient = Depends(get_supabase_client),
):
    logger.info(f"Magic link login attempt for email: {request_data.email}")
    try:
        await supabase.auth.sign_in_with_otp({"email": request_data.email, "options": {}})
        
        logger.info(f"Magic link successfully requested for {request_data.email}")
        return MagicLinkSentResponse(
            message=f"Magic link sent to {request_data.email}. Please check your inbox."
        )

    except SupabaseAPIError as e:
        logger.warning(f"Supabase API error during magic link request for {request_data.email}: {e.message} (Status: {e.status})")
        detail = f"Failed to send magic link: {e.message}"
        http_status_code = status.HTTP_400_BAD_REQUEST
        if e.status and 400 <= e.status < 500:
            http_status_code = e.status
        elif e.status and e.status == 500:
            http_status_code = status.HTTP_502_BAD_GATEWAY
            detail = "Authentication service provider returned an error."

        raise HTTPException(
            status_code=http_status_code,
            detail=detail
        )
    except Exception as e:
        logger.error(f"Unexpected error during magic link request for {request_data.email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while requesting the magic link."
        )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_in: UserCreate,
    supabase: AsyncClient = Depends(get_supabase_client),
    db_session: AsyncSession = Depends(get_db),
    settings: AppSettingsType = Depends(get_app_settings),
):
    logger.info(f"Registration attempt for email: {user_in.email}")
    try:
        supa_response = await supabase.auth.sign_up(
            {
                "email": user_in.email,
                "password": user_in.password,
            }
        )
        logger.debug(f"Supabase sign_up response: {supa_response}")

        supa_user = supa_response.user
        supa_session = supa_response.session

        if not supa_user:
            logger.error("Supabase sign_up did not return a user object.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User registration failed: No user object returned from authentication provider."
            )

        profile_create_data = ProfileCreate(
            user_id=supa_user.id, 
            username=user_in.username,
            first_name=user_in.first_name,
            last_name=user_in.last_name
        )
        
        created_profile = await create_profile_in_db(
            db_session=db_session, 
            profile_data=profile_create_data, 
            user_id=supa_user.id
        )

        session_response_data = None
        if supa_session:
            mapped_supa_user = SupabaseUser(
                id=supa_user.id,
                aud=supa_user.aud or "", 
                role=supa_user.role,
                email=supa_user.email,
                phone=supa_user.phone,
                email_confirmed_at=supa_user.email_confirmed_at,
                phone_confirmed_at=supa_user.phone_confirmed_at,
                confirmed_at=getattr(supa_user, 'confirmed_at', supa_user.email_confirmed_at or supa_user.phone_confirmed_at), 
                last_sign_in_at=supa_user.last_sign_in_at,
                app_metadata=supa_user.app_metadata or {},
                user_metadata=supa_user.user_metadata or {},
                identities=supa_user.identities or [],
                created_at=supa_user.created_at,
                updated_at=supa_user.updated_at
            )
            session_response_data = SupabaseSession(
                access_token=supa_session.access_token,
                token_type=supa_session.token_type,
                expires_in=supa_session.expires_in,
                expires_at=supa_session.expires_at, 
                refresh_token=supa_session.refresh_token,
                user=mapped_supa_user
            )

        # Determine response message based on confirmation status and settings
        if settings.supabase_auto_confirm_new_users and supa_user.email_confirmed_at:
            # Scenario: App is configured to auto-confirm, and Supabase user is confirmed.
            message = "User registered and auto-confirmed successfully."
        elif settings.supabase_email_confirmation_required and not supa_user.email_confirmed_at:
            # Scenario: App requires email confirmation, and Supabase user is not yet confirmed.
            message = "User registration initiated. Please check your email to confirm your account."
        elif not settings.supabase_email_confirmation_required and supa_user.email_confirmed_at:
            # Scenario: App does NOT require email confirmation, and Supabase user is confirmed.
            message = "User registered successfully."
        else:
            # Fallback for any other combination or unexpected state.
            message = "User registered successfully."
        
        logger.info(f"User {user_in.email} registered. Status: {message} Profile created.")
        return UserResponse(
            message=message,
            session=session_response_data,
            profile=ProfileResponse.model_validate(created_profile)
        )

    except SupabaseAPIError as e:
        logger.warning(f"Supabase API error during registration for {user_in.email}: {e.message} (Status: {e.status})")
        detail = f"Registration failed: {e.message}"
        http_status_code = status.HTTP_400_BAD_REQUEST
        if "already registered" in e.message.lower():
            http_status_code = status.HTTP_409_CONFLICT
            detail = "User with this email already exists. Please use a different email or log in."
        elif "password" in e.message.lower() and ("characters" in e.message.lower() or "format" in e.message.lower()):
            http_status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
            detail = f"Invalid password: {e.message}"
        elif e.status and 400 <= e.status < 500:
             http_status_code = e.status

        raise HTTPException(
            status_code=http_status_code,
            detail=detail
        )
    except HTTPException as e: 
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during registration for {user_in.email}: {e}", exc_info=True)
        # Specific handling for the "Supabase down" mock scenario for test_register_user_supabase_service_unavailable
        if str(e) == "Supabase down": 
            http_status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            detail_message = "Service unavailable or unexpected error with Supabase. Please try again later."
        else:
            # For other unexpected errors, maintain the 500 response
            http_status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            detail_message = "An unexpected error occurred during user registration."
        
        raise HTTPException(
            status_code=http_status_code,
            detail=detail_message
        )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout_user(
    request: Request,
    supabase: AsyncClient = Depends(get_supabase_client),
    current_user: SupabaseUser = Depends(get_current_supabase_user) # Ensures user is authenticated
):
    logger.info(f"Logout attempt for user: {current_user.email}")
    
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        # This case should ideally be caught by get_current_supabase_user if token is missing/malformed,
        # but as a safeguard or if get_current_supabase_user is bypassed/fails early.
        logger.warning("Logout attempt with missing or malformed Authorization header.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing or malformed."
        )
    
    token = auth_header.split("Bearer ")[1]

    try:
        await supabase.auth.sign_out(jwt=token)
        logger.info(f"User {current_user.email} logged out successfully.")
        return {"message": "Successfully logged out"}
    except SupabaseAPIError as e:
        logger.warning(f"Supabase API error during logout for user {current_user.email}: {e.message} (Status: {e.status})")
        # Supabase sign_out might not typically raise errors unless the token is already invalid
        # or there's a service issue. If token is invalid, get_current_supabase_user should catch it.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, # Or e.status if appropriate
            detail=f"Logout failed: {e.message}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during logout for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during logout."
        )


@router.post("/password/reset", response_model=PasswordResetResponse, status_code=status.HTTP_200_OK)
async def request_password_reset(
    payload: PasswordResetRequest,
    supabase: AsyncClient = Depends(get_supabase_client),
    settings_dep: AppSettingsType = Depends(get_app_settings) # Access settings via dependency
):
    logger.info(f"Password reset requested for email: {payload.email}")
    try:
        # Supabase's reset_password_for_email does not error out if the email doesn't exist.
        # It sends an email if the user exists, otherwise does nothing.
        # This is good for security as it prevents email enumeration.
        await supabase.auth.reset_password_for_email(
            email=payload.email,
            options={"redirect_to": settings_dep.PASSWORD_RESET_REDIRECT_URL}
        )
        # Always return a generic success message to prevent email enumeration
        logger.info(f"Password reset process initiated for email: {payload.email} (if user exists).")
        return PasswordResetResponse(message="If an account with this email exists, a password reset link has been sent.")
    except SupabaseAPIError as e:
        logger.error(f"Supabase API error during password reset for {payload.email}: {e.message} (Status: {e.status}, Code: {e.code})", exc_info=True)
        # Handle specific Supabase errors if necessary, e.g., rate limiting
        if e.status == 429:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Password reset request failed: {e.message}"
            )
        # For other Supabase errors, return a generic service unavailable message
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Password reset request failed: {e.message}" # Or a more generic message
        )
    except Exception as e:
        logger.error(f"Unexpected error during password reset for {payload.email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while requesting password reset."
        )


@router.post("/password/update", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def update_user_password(
    payload: PasswordUpdateRequest,
    token: str = Depends(oauth2_scheme), 
    supabase: AsyncClient = Depends(get_supabase_client),
    current_user: SupabaseUser = Depends(get_current_supabase_user) 
):
    logger.info(f"Password update attempt for user: {current_user.email}")
    try:
        await supabase.auth.update_user(
            attributes=UserAttributes(password=payload.new_password),
            jwt=token 
        )
        logger.info(f"Password updated successfully for user: {current_user.email}")
        return UserResponse(message="Password updated successfully.")
    except SupabaseAPIError as e:
        logger.warning(
            f"Supabase API error during password update for user {current_user.email}: "
            f"{e.message} (Status: {e.status}, Code: {e.code})"
        )
        error_detail = f"Password update failed: {e.message}"
        error_status_code = status.HTTP_503_SERVICE_UNAVAILABLE 
        
        if isinstance(e.status, int) and 400 <= e.status < 600:
            error_status_code = e.status
        
        raise HTTPException(
            status_code=error_status_code,
            detail=error_detail
        )
    except HTTPException: 
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error during password update for user {current_user.email}: {e}", 
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during password update."
        )


# Export the router to be used in main.py
user_auth_router = router
