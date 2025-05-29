from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import status, HTTPException
from httpx import AsyncClient, Response as HttpxResponse # Added Response for AuthApiError mocking
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from auth_service.main import app  # To access app.dependency_overrides
from auth_service.routers import user_auth_routes # Added import
from auth_service.supabase_client import get_supabase_client as real_get_supabase_client
from auth_service.config import settings as app_config_settings # For monkeypatching

from ..utils import create_mock_supa_session, create_mock_supa_user, create_default_mock_settings
from auth_service.schemas.user_schemas import UserLoginRequest, MagicLinkLoginRequest, MagicLinkSentResponse, SupabaseUser, PasswordResetRequest, PasswordUpdateRequest, OAuthProvider, OAuthRedirectResponse, SupabaseSession # Added for login, magic link, logout, and password reset tests
from gotrue.errors import AuthApiError # Corrected import for login error tests
from gotrue.types import UserAttributes # For password update payload
from auth_service.dependencies.user_deps import get_current_supabase_user as real_get_current_supabase_user # Placeholder for actual dependency


@pytest.mark.asyncio
async def test_register_user_placeholder(
    async_client: AsyncClient,
    db_session_for_crud: AsyncSession,  # Add database session
    monkeypatch, # Add monkeypatch
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

    try:
        # Apply mock settings for this test using monkeypatch
        monkeypatch.setattr(app_config_settings, 'supabase_email_confirmation_required', True)
        monkeypatch.setattr(app_config_settings, 'supabase_auto_confirm_new_users', False)
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
        # monkeypatch will automatically revert the setattr changes for app_config_settings


@pytest.mark.asyncio
async def test_login_user_successful(
    async_client: AsyncClient, monkeypatch # Ensure monkeypatch is present
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

    try:
        # No specific settings attributes are being changed for this test's logic.
        # The route will use the global app_config_settings via dependency injection.

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
        # monkeypatch will automatically revert the setattr changes for app_config_settings


@pytest.mark.asyncio
async def test_login_user_invalid_credentials(
    async_client: AsyncClient, monkeypatch
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

    try:
        # No specific settings attributes are being changed for this test's logic.
        # The route will use the global app_config_settings via dependency injection.

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
        # monkeypatch will automatically revert the setattr changes for app_config_settings


@pytest.mark.asyncio
async def test_login_user_not_found(
    async_client: AsyncClient, monkeypatch
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

    try:
        # No specific settings attributes are being changed for this test's logic.
        # The route will use the global app_config_settings via dependency injection.

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
        # monkeypatch will automatically revert the setattr changes for app_config_settings


@pytest.mark.asyncio
async def test_login_user_email_not_confirmed(
    async_client: AsyncClient, monkeypatch
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

    try:
        monkeypatch.setattr(app_config_settings, 'supabase_email_confirmation_required', True)

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
        # monkeypatch will automatically revert the setattr changes for app_config_settings


@pytest.mark.asyncio
async def test_login_magic_link_successful_request(
    async_client: AsyncClient, monkeypatch
):
    test_email = "magic_user@example.com"
    test_login_data = {"email": test_email}

    mock_supabase_auth = AsyncMock()
    mock_otp_response = MagicMock()
    mock_supabase_auth.sign_in_with_otp = AsyncMock(return_value=mock_otp_response)

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override

    try:
        # No specific settings attributes are being changed for this test's logic.
        # The route will use the global app_config_settings via dependency injection.

        response = await async_client.post("/auth/users/login/magiclink", json=test_login_data)

        assert response.status_code == status.HTTP_200_OK, f"Response: {response.text}"
        response_data = response.json()
        assert response_data["message"] == f"Magic link sent to {test_email}. Please check your inbox."
        # Ensure options are passed if your Supabase client setup requires them, e.g., for email redirect
        mock_supabase_auth.sign_in_with_otp.assert_called_once_with({"email": test_email, "options": {}})

    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:
                del app.dependency_overrides[real_get_supabase_client]
        # monkeypatch will automatically revert the setattr changes for app_config_settings


@pytest.mark.asyncio
async def test_login_magic_link_invalid_email_format(
    async_client: AsyncClient,
):
    test_login_data = {"email": "notanemail"}

    response = await async_client.post("/auth/users/login/magiclink", json=test_login_data)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    response_data = response.json()
    assert "detail" in response_data
    assert any(
        field_error["type"] == "value_error" and field_error["loc"] == ["body", "email"]
        for field_error in response_data["detail"]
    )


@pytest.mark.asyncio
async def test_login_magic_link_supabase_api_error(
    async_client: AsyncClient, monkeypatch
):
    test_email = "error_user@example.com"
    test_login_data = {"email": test_email}

    mock_supabase_auth = AsyncMock()
    mock_supabase_auth.sign_in_with_otp = AsyncMock(
        side_effect=AuthApiError(message="Supabase rate limit exceeded", status=429, code="rate_limit_exceeded")
    )

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override

    try:
        # No specific settings attributes are being changed for this test's logic.
        # The route will use the global app_config_settings via dependency injection.

        response = await async_client.post("/auth/users/login/magiclink", json=test_login_data)

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS, f"Response: {response.text}"
        response_data = response.json()
        assert response_data["detail"] == "Failed to send magic link: Supabase rate limit exceeded"

    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:
                del app.dependency_overrides[real_get_supabase_client]
        # monkeypatch will automatically revert the setattr changes for app_config_settings


@pytest.mark.asyncio
async def test_logout_user_successful(
    async_client: AsyncClient, monkeypatch
):
    user_id = uuid4()
    login_email = f"logout_user_{user_id.hex[:6]}@example.com"
    mock_supa_user_instance = create_mock_supa_user(email=login_email, id_val=user_id, confirmed=True)
    mock_supa_session_instance = create_mock_supa_session(user=mock_supa_user_instance)

    mock_logout_supabase_auth = AsyncMock() # Renamed for clarity
    # Mock get_user for the dependency check during logout
    mock_logout_supabase_auth.get_user = AsyncMock(return_value=MagicMock(user=mock_supa_user_instance))
    # Mock sign_out for the logout call itself
    mock_logout_supabase_auth.sign_out = AsyncMock(return_value=None) # sign_out usually returns None or raises error

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_logout_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override
    try:
        # No specific settings attributes are being changed for this test's logic.
        # The route will use the global app_config_settings via dependency injection.
        
        mock_token = mock_supa_session_instance.access_token 

        headers = {"Authorization": f"Bearer {mock_token}"}
        response = await async_client.post("/auth/users/logout", headers=headers)

        assert response.status_code == status.HTTP_200_OK, f"Response: {response.text}"
        response_data = response.json()
        assert response_data["message"] == "Successfully logged out"
        mock_logout_supabase_auth.sign_out.assert_called_once_with(jwt=mock_token)

    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:
                del app.dependency_overrides[real_get_supabase_client]
        # monkeypatch will automatically revert the setattr changes for app_config_settings


@pytest.mark.asyncio
async def test_logout_user_invalid_token_format(
    async_client: AsyncClient,
):
    headers = {"Authorization": "Bearer an_invalid_token_without_proper_structure"}
    response = await async_client.post("/auth/users/logout", headers=headers)
    
    assert response.status_code == status.HTTP_401_UNAUTHORIZED, f"Response: {response.text}"
    response_data = response.json()
    assert response_data.get("detail") == "Invalid authentication credentials"


@pytest.mark.asyncio
async def test_logout_user_no_auth_header(
    async_client: AsyncClient,
):
    response = await async_client.post("/auth/users/logout") # No headers
    assert response.status_code == status.HTTP_401_UNAUTHORIZED, f"Response: {response.text}"
    response_data = response.json()
    assert response_data.get("detail") == "Not authenticated" # This is FastAPI's default for OAuth2PasswordBearer


@pytest.mark.asyncio
async def test_logout_user_expired_token(
    async_client: AsyncClient, monkeypatch
):
    expired_token = "a_jwt_that_will_be_treated_as_expired"

    mock_supabase_auth = AsyncMock()
    mock_supabase_auth.get_user = AsyncMock(
        side_effect=AuthApiError(message="Token expired", status=401, code="token_expired")
    )

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override
    try:
        # No specific settings attributes are being changed for this test's logic.
        # The route will use the global app_config_settings via dependency injection.

        headers = {"Authorization": f"Bearer {expired_token}"}
        response = await async_client.post("/auth/users/logout", headers=headers)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED, f"Response: {response.text}"
        response_data = response.json()
        assert response_data.get("detail") == "Invalid authentication credentials"

    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:
                del app.dependency_overrides[real_get_supabase_client]
        # monkeypatch will automatically revert the setattr changes for app_config_settings


@pytest.mark.asyncio
async def test_logout_user_supabase_sign_out_error(
    async_client: AsyncClient, monkeypatch
):
    user_id = uuid4()
    login_email = f"signout_error_user_{user_id.hex[:6]}@example.com"
    mock_supa_user_instance = create_mock_supa_user(email=login_email, id_val=user_id, confirmed=True)
    mock_supa_session_instance = create_mock_supa_session(user=mock_supa_user_instance)

    mock_supabase_auth = AsyncMock()
    mock_supabase_auth.get_user = AsyncMock(return_value=MagicMock(user=mock_supa_user_instance))
    mock_supabase_auth.sign_out = AsyncMock(
        side_effect=AuthApiError(message="Supabase sign_out failed", status=500, code="signout_error")
    )

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override
    try:
        # No specific settings attributes are being changed for this test's logic.
        # The route will use the global app_config_settings via dependency injection.
        
        mock_token = mock_supa_session_instance.access_token
        headers = {"Authorization": f"Bearer {mock_token}"}
        response = await async_client.post("/auth/users/logout", headers=headers)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR, f"Response: {response.text}"
        response_data = response.json()
        assert "Logout failed: Supabase sign_out failed" in response_data.get("detail", "")

    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:
                del app.dependency_overrides[real_get_supabase_client]
        # monkeypatch will automatically revert the setattr changes for app_config_settings


@pytest.mark.asyncio
async def test_password_reset_request_successful(
    async_client: AsyncClient, monkeypatch
):
    test_email = f"reset_success_{uuid4().hex[:6]}@example.com"
    request_data = {"email": test_email}

    mock_supabase_auth = AsyncMock()
    mock_supabase_auth.reset_password_for_email = AsyncMock(return_value=None) # Supabase returns None on success

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override
    try:
        # No specific settings attributes are being changed for this test's logic.
        # The route will use the global app_config_settings via dependency injection.

        response = await async_client.post("/auth/users/password/reset", json=request_data)

        assert response.status_code == status.HTTP_200_OK, f"Response: {response.text}"
        response_data = response.json()
        assert response_data["message"] == "If an account with this email exists, a password reset link has been sent."
        mock_supabase_auth.reset_password_for_email.assert_called_once_with(email=test_email, options={'redirect_to': 'http://localhost:3000/auth/update-password'})

    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:
                del app.dependency_overrides[real_get_supabase_client]
        # monkeypatch will automatically revert the setattr changes for app_config_settings


@pytest.mark.asyncio
async def test_password_reset_request_email_not_found(
    async_client: AsyncClient, monkeypatch
):
    test_email = f"reset_notfound_{uuid4().hex[:6]}@example.com"
    request_data = {"email": test_email}

    mock_supabase_auth = AsyncMock()
    mock_supabase_auth.reset_password_for_email = AsyncMock(return_value=None) 

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override
    try:
        # No specific settings attributes are being changed for this test's logic.
        # The route will use the global app_config_settings via dependency injection.

        response = await async_client.post("/auth/users/password/reset", json=request_data)

        assert response.status_code == status.HTTP_200_OK, f"Response: {response.text}"
        response_data = response.json()
        assert response_data["message"] == "If an account with this email exists, a password reset link has been sent."
        mock_supabase_auth.reset_password_for_email.assert_called_once_with(email=test_email, options={'redirect_to': 'http://localhost:3000/auth/update-password'})

    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:
                del app.dependency_overrides[real_get_supabase_client]
        # monkeypatch will automatically revert the setattr changes for app_config_settings


@pytest.mark.asyncio
async def test_password_reset_request_invalid_email_format(
    async_client: AsyncClient, monkeypatch
):
    request_data = {"email": "invalid-email"}
    response = await async_client.post("/auth/users/password/reset", json=request_data)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, f"Response: {response.text}"
    response_data = response.json()
    assert "value is not a valid email address" in response_data["detail"][0]["msg"]


@pytest.mark.asyncio
async def test_password_reset_request_supabase_api_error_rate_limit(
    async_client: AsyncClient, monkeypatch
):
    test_email = f"reset_rate_limit_{uuid4().hex[:6]}@example.com"
    request_data = {"email": test_email}

    mock_supabase_auth = AsyncMock()
    mock_supabase_auth.reset_password_for_email = AsyncMock(
        side_effect=AuthApiError(message="Rate limit exceeded", status=429, code="rate_limit_exceeded")
    )

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override
    try:
        # No specific settings attributes are being changed for this test's logic.
        # The route will use the global app_config_settings via dependency injection.

        response = await async_client.post("/auth/users/password/reset", json=request_data)

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS, f"Response: {response.text}"
        response_data = response.json()
        assert response_data["detail"] == "Password reset request failed: Rate limit exceeded"

    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:
                del app.dependency_overrides[real_get_supabase_client]
        # monkeypatch will automatically revert the setattr changes for app_config_settings


@pytest.mark.asyncio
async def test_password_reset_request_supabase_api_error_generic(
    async_client: AsyncClient, monkeypatch
):
    test_email = f"reset_generic_error_{uuid4().hex[:6]}@example.com"
    request_data = {"email": test_email}

    mock_supabase_auth = AsyncMock()
    mock_supabase_auth.reset_password_for_email = AsyncMock(
        side_effect=AuthApiError(message="Some generic Supabase error", status=500, code="generic_error")
    )

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override
    try:
        # No specific settings attributes are being changed for this test's logic.
        # The route will use the global app_config_settings via dependency injection.

        response = await async_client.post("/auth/users/password/reset", json=request_data)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE, f"Response: {response.text}"
        response_data = response.json()
        assert response_data["detail"] == "Password reset request failed: Some generic Supabase error"

    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides:
                del app.dependency_overrides[real_get_supabase_client]
        # monkeypatch will automatically revert the setattr changes for app_config_settings


@pytest.mark.asyncio
async def test_password_update_successful(
    async_client: AsyncClient, monkeypatch
):
    """
    Test successful password update for an authenticated user.
    """
    mock_user_id = uuid4()
    mock_current_user = create_mock_supa_user(id_val=mock_user_id, email="testuser@example.com")
    new_password = "NewSecurePassword123!"

    # Mock the get_current_supabase_user dependency
    async def mock_get_current_user_override():
        return mock_current_user

    # Mock Supabase client's auth.update_user method
    # Supabase update_user returns a response with a user object
    mock_updated_supa_user_response = MagicMock()
    mock_updated_supa_user_response.user = create_mock_supa_user(
        id_val=mock_user_id, email="testuser@example.com" # Simulate user object returned after update
    )

    mock_supabase_auth = AsyncMock()
    mock_supabase_auth.update_user = AsyncMock(return_value=mock_updated_supa_user_response)

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    # Store original dependency overrides to restore them later
    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    original_get_current_user = app.dependency_overrides.get(real_get_current_supabase_user) 

    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override
    app.dependency_overrides[real_get_current_supabase_user] = mock_get_current_user_override

    try:
        response = await async_client.post(
            "/auth/users/password/update",
            json={"new_password": new_password},
            headers={"Authorization": f"Bearer mock_access_token_for_{mock_user_id}"} 
        )

        assert response.status_code == status.HTTP_200_OK, f"Response: {response.text}"
        response_data = response.json()
        assert response_data["message"] == "Password updated successfully."

        mock_supabase_auth.update_user.assert_called_once()
        
        call_args = mock_supabase_auth.update_user.call_args
        assert call_args is not None, "update_user was not called with any arguments"
        
        # Check keyword arguments
        assert "attributes" in call_args.kwargs
        user_attributes_arg = call_args.kwargs["attributes"]
        assert isinstance(user_attributes_arg, dict), "UserAttributes should be a dict"
        assert "password" in user_attributes_arg, "Password key missing in UserAttributes"
        assert user_attributes_arg["password"] == new_password
        
        assert "jwt" in call_args.kwargs
        # The token passed to update_user should be the one extracted by oauth2_scheme from the header
        assert call_args.kwargs["jwt"] == f"mock_access_token_for_{mock_user_id}" 

    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides: 
                del app.dependency_overrides[real_get_supabase_client]
        
        if original_get_current_user:
            app.dependency_overrides[real_get_current_supabase_user] = original_get_current_user
        else:
            if real_get_current_supabase_user in app.dependency_overrides: 
                del app.dependency_overrides[real_get_current_supabase_user]


@pytest.mark.asyncio
async def test_password_update_weak_password(
    async_client: AsyncClient, monkeypatch
):
    """
    Test password update attempt with a weak password.
    Simulates Supabase rejecting the password due to strength policies.
    """
    mock_user_id = uuid4()
    mock_current_user = create_mock_supa_user(id_val=mock_user_id, email="testuser@example.com")
    weak_password = "weak" # Example of a weak password

    # Mock the get_current_supabase_user dependency
    async def mock_get_current_user_override():
        return mock_current_user

    # Mock Supabase client's auth.update_user to simulate weak password error
    mock_supabase_auth = AsyncMock()
    weak_password_error_message = "Password should be stronger." # Or a more specific Supabase message
    mock_supabase_auth.update_user = AsyncMock(
        side_effect=AuthApiError(
            message=weak_password_error_message, 
            status=status.HTTP_422_UNPROCESSABLE_ENTITY, 
            code="weak_password" # Hypothetical error code from Supabase
        )
    )

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth

    async def mock_get_supabase_override():
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    original_get_current_user = app.dependency_overrides.get(real_get_current_supabase_user)

    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override
    app.dependency_overrides[real_get_current_supabase_user] = mock_get_current_user_override

    try:
        response = await async_client.post(
            "/auth/users/password/update",
            json={"new_password": weak_password},
            headers={"Authorization": f"Bearer mock_access_token_for_{mock_user_id}"}
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, f"Response: {response.text}"
        response_data = response.json()
        # Check for Pydantic validation error structure
        assert isinstance(response_data["detail"], list)
        assert len(response_data["detail"]) == 1
        detail_error = response_data["detail"][0]
        assert detail_error["type"] == "string_too_short"
        assert detail_error["loc"] == ["body", "new_password"]
        assert "ctx" in detail_error and detail_error["ctx"]["min_length"] == 8
        assert detail_error["input"] == weak_password
        assert "String should have at least 8 characters" in detail_error["msg"]

        # Ensure Supabase update_user was NOT called because Pydantic validation failed first
        mock_supabase_auth.update_user.assert_not_called()

    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides: # pragma: no cover
                del app.dependency_overrides[real_get_supabase_client]
        
        if original_get_current_user:
            app.dependency_overrides[real_get_current_supabase_user] = original_get_current_user
        else:
            if real_get_current_supabase_user in app.dependency_overrides: # pragma: no cover
                del app.dependency_overrides[real_get_current_supabase_user]


@pytest.mark.asyncio
async def test_password_update_invalid_token(
    async_client: AsyncClient, monkeypatch
):
    """
    Test password update attempt with an invalid/expired authentication token.
    """
    new_password = "NewSecurePassword123!"
    expected_error_detail = "Invalid authentication credentials" # Or whatever the actual dependency raises

    # Mock the get_current_supabase_user dependency to raise an auth error
    async def mock_get_current_user_auth_error():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail=expected_error_detail
        )

    # No need to mock supabase_client.auth.update_user as it shouldn't be called
    mock_supabase_auth = AsyncMock()
    mock_supabase_auth.update_user = AsyncMock() # Define it so it can be checked if called

    mock_supabase_client_instance = AsyncMock()
    mock_supabase_client_instance.auth = mock_supabase_auth
    
    async def mock_get_supabase_override(): # Still need to provide the supabase client
        return mock_supabase_client_instance

    original_get_supabase = app.dependency_overrides.get(real_get_supabase_client)
    original_get_current_user = app.dependency_overrides.get(real_get_current_supabase_user)

    app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override
    app.dependency_overrides[real_get_current_supabase_user] = mock_get_current_user_auth_error

    try:
        response = await async_client.post(
            "/auth/users/password/update",
            json={"new_password": new_password},
            headers={"Authorization": "Bearer an_invalid_or_expired_token"} # Provide an invalid token
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED, f"Response: {response.text}"
        response_data = response.json()
        assert response_data["detail"] == expected_error_detail

        # Ensure Supabase update_user was NOT called
        mock_supabase_auth.update_user.assert_not_called()

    finally:
        if original_get_supabase:
            app.dependency_overrides[real_get_supabase_client] = original_get_supabase
        else:
            if real_get_supabase_client in app.dependency_overrides: # pragma: no cover
                del app.dependency_overrides[real_get_supabase_client]
        
        if original_get_current_user:
            app.dependency_overrides[real_get_current_supabase_user] = original_get_current_user
        else:
            if real_get_current_supabase_user in app.dependency_overrides: # pragma: no cover
                del app.dependency_overrides[real_get_current_supabase_user]

