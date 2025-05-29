from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import status
from httpx import AsyncClient, Response as HttpxResponse # Added Response for AuthApiError mocking
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from auth_service.main import app  # To access app.dependency_overrides
from auth_service.routers import user_auth_routes # Added import
from auth_service.supabase_client import get_supabase_client as real_get_supabase_client

from ..utils import create_mock_supa_session, create_mock_supa_user, create_default_mock_settings
from auth_service.schemas.user_schemas import UserLoginRequest # Added for login tests
from gotrue.errors import AuthApiError # Corrected import for login error tests


@pytest.mark.asyncio
async def test_register_user_placeholder(
    async_client: AsyncClient,
    db_session_for_crud: AsyncSession,  # Add database session
):
    """
    Test the placeholder /auth/users/register endpoint.
    Ensures it's reachable and returns the expected mock structure.
    """
    user_id = uuid4()
    test_user_data = {
        "email": f"placeholder_user_{user_id.hex[:6]}@example.com",
        "password": "aSecurePassword123",
        "username": f"testuser_{user_id.hex[:6]}",
        "first_name": "Test",
        "last_name": "User",
    }

    # Insert dummy user to satisfy FK constraint for profile creation
    await db_session_for_crud.execute(
        text(
            "INSERT INTO auth.users (id, email, encrypted_password, role) VALUES (:id, :email, 'dummy_password', 'authenticated') ON CONFLICT (id) DO NOTHING;"
        ),
        {"id": user_id, "email": test_user_data["email"]},
    )
    await db_session_for_crud.commit()

    # Mock Supabase client for this specific test
    mock_supa_user_instance = create_mock_supa_user(
        email=test_user_data["email"], id_val=user_id, confirmed=False # Expecting email confirmation
    )
    mock_supa_session_instance = create_mock_supa_session(user=mock_supa_user_instance)

    # Create a mock response object similar to what Supabase client returns
    mock_auth_response = MagicMock()
    mock_auth_response.user = mock_supa_user_instance
    mock_auth_response.session = mock_supa_session_instance

    mock_supabase_auth = AsyncMock()
    # Ensure sign_up returns the mock_auth_response directly
    mock_supabase_auth.sign_up = AsyncMock(return_value=mock_auth_response)

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override

    original_route_settings = user_auth_routes.settings # Store original settings
    try:
        # Apply mock settings for this test
        current_mock_settings = create_default_mock_settings()
        # Ensure email confirmation is required for this placeholder test's expectation
        current_mock_settings.supabase_email_confirmation_required = True 
        current_mock_settings.supabase_auto_confirm_new_users = False # Explicitly set for clarity
        user_auth_routes.settings = current_mock_settings
        response = await async_client.post("/auth/users/register", json=test_user_data)

        assert (
            response.status_code == status.HTTP_201_CREATED
        ), f"Response: {response.text}"

        response_data = response.json()
        assert "message" in response_data
        assert (
            response_data["message"]
            == "User registration initiated. Please check your email to confirm your account."
        )

        assert "session" in response_data
        assert response_data["session"] is not None
        assert "access_token" in response_data["session"]
        assert response_data["session"]["access_token"] == f"mock_access_token_for_{mock_supa_user_instance.id}"
        assert "user" in response_data["session"]
        assert response_data["session"]["user"]["email"] == test_user_data["email"]

        assert "profile" in response_data
        assert response_data["profile"] is not None
        assert response_data["profile"]["username"] == test_user_data["username"]
        assert (
            response_data["profile"]["user_id"]
            == response_data["session"]["user"]["id"]
        )

    finally:
        # Clean up override
        # Clean up override for supabase client
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:
                del app.dependency_overrides[real_get_supabase_client]
        # Restore original settings
        user_auth_routes.settings = original_route_settings


@pytest.mark.asyncio
async def test_login_user_successful(
    async_client: AsyncClient,
):
    user_id = uuid4()
    test_login_data = {
        "email": f"login_user_{user_id.hex[:6]}@example.com",
        "password": "aSecurePassword123",
    }

    mock_supa_user_instance = create_mock_supa_user(
        email=test_login_data["email"], id_val=user_id, confirmed=True
    )
    mock_supa_session_instance = create_mock_supa_session(user=mock_supa_user_instance)

    mock_auth_response = MagicMock()
    mock_auth_response.user = mock_supa_user_instance
    mock_auth_response.session = mock_supa_session_instance

    mock_supabase_auth = AsyncMock()
    mock_supabase_auth.sign_in_with_password = AsyncMock(return_value=mock_auth_response)

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override

    original_route_settings = user_auth_routes.settings
    try:
        current_mock_settings = create_default_mock_settings()
        user_auth_routes.settings = current_mock_settings

        response = await async_client.post("/auth/users/login", json=test_login_data)

        assert response.status_code == status.HTTP_200_OK, f"Response: {response.text}"
        response_data = response.json()
        assert "access_token" in response_data
        assert response_data["access_token"] == f"mock_access_token_for_{mock_supa_user_instance.id}"
        assert "user" in response_data
        assert response_data["user"]["email"] == test_login_data["email"]
        assert response_data["user"]["id"] == str(user_id)

    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:
                del app.dependency_overrides[real_get_supabase_client]
        user_auth_routes.settings = original_route_settings


@pytest.mark.asyncio
async def test_login_user_invalid_credentials(
    async_client: AsyncClient,
):
    test_login_data = {
        "email": "user@example.com",
        "password": "wrongPassword123",
    }

    mock_supabase_auth = AsyncMock()
    mock_supabase_auth.sign_in_with_password = AsyncMock(
        side_effect=AuthApiError("Invalid login credentials", status=400, code="invalid_grant")
    )

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override

    original_route_settings = user_auth_routes.settings
    try:
        current_mock_settings = create_default_mock_settings()
        user_auth_routes.settings = current_mock_settings

        response = await async_client.post("/auth/users/login", json=test_login_data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED, f"Response: {response.text}"
        response_data = response.json()
        assert response_data["detail"] == "Invalid login credentials"

    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:
                del app.dependency_overrides[real_get_supabase_client]
        user_auth_routes.settings = original_route_settings


@pytest.mark.asyncio
async def test_login_user_not_found(
    async_client: AsyncClient,
):
    test_login_data = {
        "email": "nonexistent_user@example.com",
        "password": "anyPassword123",
    }

    mock_supabase_auth = AsyncMock()
    # Supabase might return a generic "Invalid login credentials" for non-existent users too
    # to avoid user enumeration attacks.
    mock_supabase_auth.sign_in_with_password = AsyncMock(
        side_effect=AuthApiError("Invalid login credentials", status=400, code="invalid_grant")
    )

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override

    original_route_settings = user_auth_routes.settings
    try:
        current_mock_settings = create_default_mock_settings()
        user_auth_routes.settings = current_mock_settings

        response = await async_client.post("/auth/users/login", json=test_login_data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED, f"Response: {response.text}"
        response_data = response.json()
        assert response_data["detail"] == "Invalid login credentials" # Assuming generic message

    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:
                del app.dependency_overrides[real_get_supabase_client]
        user_auth_routes.settings = original_route_settings


@pytest.mark.asyncio
async def test_login_user_email_not_confirmed(
    async_client: AsyncClient,
):
    user_id = uuid4()
    test_login_data = {
        "email": f"unconfirmed_{user_id.hex[:6]}@example.com",
        "password": "aSecurePassword123",
    }

    mock_supabase_auth = AsyncMock()
    # Mock Supabase returning an error for unconfirmed email
    mock_response_unconfirmed = HttpxResponse(status_code=400, json={'error': 'access_denied', 'error_description': 'Email not confirmed'})
    mock_supabase_auth.sign_in_with_password = AsyncMock(
            side_effect=AuthApiError(message="Email not confirmed", status=mock_response_unconfirmed.status_code, code="access_denied")
        )

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override

    original_route_settings = user_auth_routes.settings
    try:
        current_mock_settings = create_default_mock_settings()
        current_mock_settings.supabase_email_confirmation_required = True # Ensure this setting is active
        user_auth_routes.settings = current_mock_settings

        response = await async_client.post("/auth/users/login", json=test_login_data)

        # Expecting a 401 or 403 if email confirmation is required and not met
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, f"Response: {response.text}"
        response_data = response.json()
        assert response_data["detail"] == "Email not confirmed. Please check your inbox."

    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:
                del app.dependency_overrides[real_get_supabase_client]
        user_auth_routes.settings = original_route_settings
