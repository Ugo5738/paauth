from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, ConfigDict


# --- Profile Schemas ---
class ProfileBase(BaseModel):
    username: Optional[str] = Field(None, max_length=50)
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)


class ProfileCreate(ProfileBase):
    user_id: UUID  # Will be populated from Supabase user ID


class ProfileResponse(ProfileBase):
    user_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Supabase Schemas (mirroring supabase-py structure) ---
class SupabaseUser(BaseModel):
    id: UUID
    aud: str
    role: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    email_confirmed_at: Optional[datetime] = None
    phone_confirmed_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = (
        None  # Generally an alias for email_confirmed_at or phone_confirmed_at
    )
    last_sign_in_at: Optional[datetime] = None
    app_metadata: Dict[str, Any] = Field(default_factory=dict)
    user_metadata: Dict[str, Any] = Field(default_factory=dict)
    identities: Optional[List[Dict[str, Any]]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SupabaseSession(
    BaseModel
):  # Renamed from SupabaseUserSession for clarity if used elsewhere
    access_token: str
    token_type: str = "bearer"
    expires_in: Optional[int] = None
    expires_at: Optional[datetime] = None  # Supabase-py returns this as datetime
    refresh_token: Optional[str] = None
    user: SupabaseUser

    model_config = ConfigDict(from_attributes=True)

from enum import Enum

# --- User Authentication Schemas ---

class OAuthProvider(str, Enum):
    GOOGLE = "google"
    GITHUB = "github"
    # Add other providers as needed, e.g., AZURE = "azure"


class OAuthRedirectResponse(BaseModel):
    authorization_url: str

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class MagicLinkLoginRequest(BaseModel):
    email: EmailStr


class MagicLinkSentResponse(BaseModel):
    message: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetResponse(BaseModel):
    message: str


class PasswordUpdateRequest(BaseModel):
    new_password: str = Field(..., min_length=8) # Enforce min_length, same as registration


# --- User Registration Schemas ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(
        ..., min_length=8
    )  # Ensure password meets complexity if needed
    username: Optional[str] = Field(None, max_length=50)
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    # Any other data to be passed to Supabase sign_up options (e.g., data for user_metadata)
    # data: Optional[Dict[str, Any]] = None # If you want to pass extra data to Supabase user_metadata


class UserResponse(BaseModel):
    message: str
    session: Optional[SupabaseSession] = (
        None  # Session can be None if email confirmation is pending
    )
    profile: Optional[ProfileResponse] = (
        None  # Profile might not be created if Supabase signup fails or is pending
    )

    model_config = ConfigDict(from_attributes=True)
