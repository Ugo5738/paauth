import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from supabase._async.client import AsyncClient
from gotrue.errors import AuthApiError

from auth_service.main import app
from auth_service.config import settings
from auth_service.dependencies import get_app_settings


@pytest.fixture
def test_settings():
    """Test settings fixture"""
    mock_settings = MagicMock()
    mock_settings.ENVIRONMENT = "test"
    mock_settings.EMAIL_CONFIRMATION_REDIRECT_URL = "http://localhost:3000/confirm-email"
    return mock_settings


@pytest.fixture
def mock_supabase():
    """Mock Supabase client"""
    client = AsyncMock(spec=AsyncClient)
    client.auth = AsyncMock()
    client.auth.reset_password_for_email = AsyncMock()
    return client


@pytest.fixture
def client(mock_supabase, test_settings):
    """Test client fixture with mocked dependencies"""
    # Need to properly override the FastAPI dependency for Supabase client
    # And store the original dependency to restore it later
    from auth_service.supabase_client import get_supabase_client
    
    original_dependencies = app.dependency_overrides.copy()
    app.dependency_overrides[get_app_settings] = lambda: test_settings
    app.dependency_overrides[get_supabase_client] = lambda: mock_supabase
    
    with TestClient(app) as test_client:
        yield test_client
    
    # Restore original dependencies
    app.dependency_overrides = original_dependencies


def test_resend_email_verification_success(client, mock_supabase):
    """Test successful email verification resend"""
    # Configure mock to return successfully
    mock_supabase.auth.reset_password_for_email.return_value = None
    
    # Make request to resend verification
    response = client.post(
        "/auth/users/verify/resend",
        json={"email": "test@example.com"}
    )
    
    # Verify response
    assert response.status_code == status.HTTP_200_OK
    assert "message" in response.json()
    assert "Verification email resent" in response.json()["message"]
    
    # Verify Supabase was called with correct parameters
    mock_supabase.auth.reset_password_for_email.assert_called_once_with(
        email="test@example.com",
        options={"email_redirect_to": "http://localhost:3000/confirm-email"}
    )


def test_resend_email_verification_user_not_found(client, mock_supabase):
    """Test email verification resend when user not found"""
    # Configure mock to raise a user not found error
    error = AuthApiError(message="User not found", status=400, code="400")
    mock_supabase.auth.reset_password_for_email.side_effect = error
    
    # Make request to resend verification
    response = client.post(
        "/auth/users/verify/resend",
        json={"email": "nonexistent@example.com"}
    )
    
    # Verify response - should still return 200 to avoid leaking info
    assert response.status_code == status.HTTP_200_OK
    assert "message" in response.json()
    assert "If your email exists" in response.json()["message"]


def test_resend_email_verification_already_verified(client, mock_supabase):
    """Test email verification resend when email already verified"""
    # Configure mock to raise an already verified error
    error = AuthApiError(message="Email already confirmed", status=400, code="400")
    mock_supabase.auth.reset_password_for_email.side_effect = error
    
    # Make request to resend verification
    response = client.post(
        "/auth/users/verify/resend",
        json={"email": "verified@example.com"}
    )
    
    # Verify response
    assert response.status_code == status.HTTP_200_OK
    assert "message" in response.json()
    assert "already verified" in response.json()["message"]


def test_resend_email_verification_service_error(client, mock_supabase):
    """Test email verification resend when Supabase service has an error"""
    # Configure mock to raise a general service error
    error = AuthApiError(message="Service unavailable", status=503, code="503")
    mock_supabase.auth.reset_password_for_email.side_effect = error
    
    # Make request to resend verification
    response = client.post(
        "/auth/users/verify/resend",
        json={"email": "test@example.com"}
    )
    
    # Verify response
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "detail" in response.json()
    assert "Error processing email verification" in response.json()["detail"]
