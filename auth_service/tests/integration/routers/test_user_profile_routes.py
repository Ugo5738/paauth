# Standard library imports
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

# Third-party imports
import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# Application-specific imports
from auth_service.main import app
from auth_service.models.profile import Profile  # SQLAlchemy model
from auth_service.schemas.user_schemas import ProfileResponse # Pydantic model
from auth_service.routers.user_auth_routes import get_current_supabase_user # Dependency to mock
from tests.utils import create_mock_supa_user # Test utility


@pytest.mark.asyncio
async def test_get_user_profile_me_successful(
    async_client: AsyncClient,
    db_session_for_crud: AsyncSession,
    monkeypatch,
):
    """Test successful retrieval of the current user's profile."""
    mock_user_id = uuid4()
    mock_email = f"user_{mock_user_id.hex[:8]}@example.com"
    mock_username = f"testuser_{mock_user_id.hex[:8]}"

    # 1. Create a mock Supabase user (as would be returned by the dependency)
    mock_supa_user = create_mock_supa_user(id_val=mock_user_id, email=mock_email)

    # 2. Create a profile in the database for this user
    profile_data = {
        "user_id": mock_user_id,
        "email": mock_email,
        "username": mock_username,
        "first_name": "Test",
        "last_name": "User",
        "is_active": True,
        # created_at and updated_at will be set by the DB
    }
    new_profile = Profile(**profile_data)
    db_session_for_crud.add(new_profile)
    await db_session_for_crud.commit()
    await db_session_for_crud.refresh(new_profile)

    # 3. Mock the get_current_supabase_user dependency
    async def mock_get_current_user_override():
        return mock_supa_user

    original_dependency = app.dependency_overrides.get(get_current_supabase_user)
    app.dependency_overrides[get_current_supabase_user] = mock_get_current_user_override

    try:
        # 4. Make the request to the endpoint
        response = await async_client.get(
            "/auth/users/me", 
            headers={"Authorization": "Bearer faketoken"} # Token is needed for dependency
        )

        # 5. Assertions
        assert response.status_code == status.HTTP_200_OK, response.text
        response_data = response.json()
        
        # Validate against Pydantic model (implicitly done by parsing)
        profile_response = ProfileResponse(**response_data)

        assert profile_response.user_id == mock_user_id
        assert profile_response.email == mock_email
        assert profile_response.username == mock_username
        assert profile_response.first_name == "Test"
        assert profile_response.last_name == "User"
        assert profile_response.is_active is True
        assert isinstance(profile_response.created_at, datetime)
        assert isinstance(profile_response.updated_at, datetime)
        # Check if datetimes are timezone-aware (assuming they should be)
        assert profile_response.created_at.tzinfo is not None
        assert profile_response.updated_at.tzinfo is not None

    finally:
        # Restore original dependency
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            del app.dependency_overrides[get_current_supabase_user]


@pytest.mark.asyncio
async def test_get_user_profile_me_profile_not_found(
    async_client: AsyncClient,
    db_session_for_crud: AsyncSession, # db_session needed to ensure no profile exists
    monkeypatch,
):
    """Test profile retrieval when authenticated user has no local profile (edge case)."""
    mock_user_id = uuid4()
    mock_email = f"no_profile_user_{mock_user_id.hex[:8]}@example.com"

    # 1. Create a mock Supabase user
    mock_supa_user = create_mock_supa_user(id_val=mock_user_id, email=mock_email)

    # 2. Ensure NO profile exists in the database for this user_id.
    # (No action needed as db_session_for_crud is clean for this test unless a profile was created)

    # 3. Mock the get_current_supabase_user dependency
    async def mock_get_current_user_override():
        return mock_supa_user

    original_dependency = app.dependency_overrides.get(get_current_supabase_user)
    app.dependency_overrides[get_current_supabase_user] = mock_get_current_user_override

    try:
        # 4. Make the request
        response = await async_client.get(
            "/auth/users/me",
            headers={"Authorization": "Bearer faketoken"}
        )

        # 5. Assertions
        assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
        response_data = response.json()
        assert "Profile not found for user" in response_data["detail"]
        assert str(mock_user_id) in response_data["detail"]

    finally:
        # Restore original dependency
        if original_dependency:
            app.dependency_overrides[get_current_supabase_user] = original_dependency
        else:
            del app.dependency_overrides[get_current_supabase_user]


@pytest.mark.asyncio
async def test_get_user_profile_me_unauthenticated(
    async_client: AsyncClient,
):
    """Test profile retrieval when user is not authenticated."""
    # 1. Make the request without an Authorization header
    response = await async_client.get("/auth/users/me")

    # 2. Assertions
    # FastAPI's OAuth2PasswordBearer returns 401 if token is missing/invalid
    assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text
    response_data = response.json()
    assert response_data["detail"] == "Not authenticated"
