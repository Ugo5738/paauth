from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func as sql_func
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# New imports for dependency overrides
from auth_service.main import app
from auth_service.models import Profile
from auth_service.routers import user_auth_routes
from auth_service.routers.user_auth_routes import get_profile_by_user_id_from_db
from auth_service.supabase_client import get_supabase_client as real_get_supabase_client

from ..utils import create_mock_supa_session, create_mock_supa_user, create_default_mock_settings



@pytest.mark.asyncio
async def test_register_user_successful_email_confirmation_required(
    async_client: AsyncClient, db_session_for_crud: AsyncSession
):
    user_id = uuid4()
    user_email = f"testconfirm_{user_id.hex[:8]}@example.com"
    user_password = "ValidPassword123!"
    user_username = f"testuserconfirm_{user_id.hex[:8]}"

    mock_user_data = create_mock_supa_user(
        email=user_email, id_val=user_id, confirmed=False
    )
    mock_session_data = create_mock_supa_session(user=mock_user_data)

    # Insert dummy user to satisfy FK constraint for profile creation
    await db_session_for_crud.execute(
        text(
            "INSERT INTO auth.users (id, email, encrypted_password, role) VALUES (:id, :email, 'dummy_password', 'authenticated') ON CONFLICT (id) DO NOTHING;"
        ),
        {"id": user_id, "email": user_email},
    )
    await db_session_for_crud.commit()

    resolved_signup_response = MagicMock()
    resolved_signup_response.user = mock_user_data
    resolved_signup_response.session = mock_session_data

    async def mock_get_supabase_override():
        mock_supabase_client = AsyncMock()
        mock_supabase_client.auth.sign_up = AsyncMock(
            return_value=resolved_signup_response
        )
        return mock_supabase_client

    original_route_settings = user_auth_routes.settings
    try:
        app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override

        current_mock_settings = create_default_mock_settings()
        current_mock_settings.supabase_email_confirmation_required = True
        current_mock_settings.supabase_auto_confirm_new_users = False
        user_auth_routes.settings = current_mock_settings

        response = await async_client.post(
            "/auth/users/register",
            json={
                "email": user_email,
                "password": user_password,
                "username": user_username,
                "first_name": "Test",
                "last_name": "UserConfirm",
            },
        )

        assert response.status_code == 201, f"Response: {response.text}"
        response_data = response.json()
        assert (
            response_data["message"] == "User registration initiated. Please check your email to confirm your account."
        )
        assert response_data["session"]["user"]["id"] == str(user_id)

        # Verify profile using the same test-managed session
        profile = await get_profile_by_user_id_from_db(
            db_session=db_session_for_crud, user_id=UUID(response_data["session"]["user"]["id"])
        )
        assert profile is not None
        assert profile.username == user_username
        assert profile.is_active is True
    finally:
        if real_get_supabase_client in app.dependency_overrides:
            del app.dependency_overrides[real_get_supabase_client]
        user_auth_routes.settings = original_route_settings


@pytest.mark.asyncio
async def test_register_user_successful_auto_confirmed(
    async_client: AsyncClient, db_session_for_crud: AsyncSession
):
    user_id = uuid4()
    user_email = f"autoconf_{user_id.hex[:8]}@example.com"
    user_password = "ValidPassword123!"
    user_username = f"autoconfuser_{user_id.hex[:8]}"

    mock_user_data = create_mock_supa_user(
        email=user_email, id_val=user_id, confirmed=True
    )
    mock_session_data = create_mock_supa_session(user=mock_user_data)

    # Insert dummy user to satisfy FK constraint for profile creation
    await db_session_for_crud.execute(
        text(
            "INSERT INTO auth.users (id, email, encrypted_password, role) VALUES (:id, :email, 'dummy_password', 'authenticated') ON CONFLICT (id) DO NOTHING;"
        ),
        {"id": user_id, "email": user_email},
    )
    await db_session_for_crud.commit()

    resolved_signup_response = MagicMock()
    resolved_signup_response.user = mock_user_data
    resolved_signup_response.session = mock_session_data

    async def mock_get_supabase_override():
        mock_supabase_client = AsyncMock()
        mock_supabase_client.auth.sign_up = AsyncMock(
            return_value=resolved_signup_response
        )
        return mock_supabase_client

    original_route_settings = user_auth_routes.settings
    try:
        app.dependency_overrides[real_get_supabase_client] = mock_get_supabase_override

        current_mock_settings = create_default_mock_settings()
        current_mock_settings.supabase_email_confirmation_required = False
        current_mock_settings.supabase_auto_confirm_new_users = True
        user_auth_routes.settings = current_mock_settings

        response = await async_client.post(
            "/auth/users/register",
            json={
                "email": user_email,
                "password": user_password,
                "username": user_username,
                "first_name": "Auto",
                "last_name": "Confirm",
            },
        )

        assert response.status_code == 201, f"Response: {response.text}"
        response_data = response.json()
        assert (
            response_data["message"]
            == "User registered and auto-confirmed successfully."
        )
        assert response_data["session"]["user"]["id"] == str(user_id)
        assert "access_token" in response_data["session"]

        profile = await get_profile_by_user_id_from_db(
            db_session=db_session_for_crud, user_id=UUID(response_data["session"]["user"]["id"])
        )
        assert profile is not None
    finally:
        if real_get_supabase_client in app.dependency_overrides:
            del app.dependency_overrides[real_get_supabase_client]
        user_auth_routes.settings = original_route_settings


@pytest.mark.asyncio
async def test_register_user_email_already_exists(async_client: AsyncClient):
    from gotrue.errors import AuthApiError

    user_email = f"existing_{uuid4().hex[:8]}@example.com"
    mock_supabase_api_error = AuthApiError(
        message="User already registered", status=400, code="user_already_exists"
    )

    async def mock_get_supabase_override_email_exists():
        mock_supabase_client = AsyncMock()
        mock_supabase_client.auth.sign_up = AsyncMock(
            side_effect=mock_supabase_api_error
        )
        return mock_supabase_client

    original_route_settings = user_auth_routes.settings
    try:
        app.dependency_overrides[real_get_supabase_client] = (
            mock_get_supabase_override_email_exists
        )
        user_auth_routes.settings = create_default_mock_settings()

        response = await async_client.post(
            "/auth/users/register",
            json={
                "email": user_email,
                "password": "ValidPass123!",
                "username": "existinguser",
                "first_name": "Existing",
                "last_name": "User",
            },
        )
        assert response.status_code == 409, f"Response: {response.text}"
        response_data = response.json()
        assert "User with this email already exists" in response_data["detail"]
    finally:
        if real_get_supabase_client in app.dependency_overrides:
            del app.dependency_overrides[real_get_supabase_client]
        user_auth_routes.settings = original_route_settings


@pytest.mark.asyncio
async def test_register_user_invalid_password_format(async_client: AsyncClient):
    user_email = f"weakpass_{uuid4().hex[:8]}@example.com"
    response = await async_client.post(
        "/auth/users/register",
        json={
            "email": user_email,
            "password": "short",  # Invalid password, too short
            "username": "weakpassuser",
        },
    )
    assert response.status_code == 422, f"Response: {response.text}"
    error_details = response.json()["detail"]
    assert isinstance(error_details, list)
    assert len(error_details) > 0
    password_error_found = False
    for error in error_details:
        if (
            isinstance(error, dict)
            and error.get("type") == "string_too_short"
            and isinstance(error.get("loc"), list)
            and len(error.get("loc")) > 1
            and error["loc"][0] == "body"
            and error["loc"][1] == "password"
        ):
            password_error_found = True
            assert "String should have at least 8 characters" in error.get("msg", "")
            break
    assert password_error_found, "Pydantic password length validation error not found."


@pytest.mark.asyncio
async def test_register_user_supabase_service_unavailable(async_client: AsyncClient):
    async def mock_get_supabase_override_service_unavailable():
        mock_supabase_client = AsyncMock()
        mock_auth_object = MagicMock()

        async def mock_sign_up_generic_error_func(*args, **kwargs):
            raise Exception("Supabase down")

        mock_auth_object.sign_up = mock_sign_up_generic_error_func
        mock_supabase_client.auth = mock_auth_object
        return mock_supabase_client

    original_route_settings = user_auth_routes.settings
    try:
        app.dependency_overrides[real_get_supabase_client] = (
            mock_get_supabase_override_service_unavailable
        )
        user_auth_routes.settings = create_default_mock_settings()

        response = await async_client.post(
            "/auth/users/register",
            json={
                "email": f"unavailable_{uuid4().hex[:8]}@example.com",
                "password": "ValidPassword123!",
                "username": "unavailableuser",
            },
        )
        assert response.status_code == 503, f"Response: {response.text}"
        assert (
            "Service unavailable or unexpected error with Supabase"
            in response.json()["detail"]
        )
    finally:
        if real_get_supabase_client in app.dependency_overrides:
            del app.dependency_overrides[real_get_supabase_client]
        user_auth_routes.settings = original_route_settings
