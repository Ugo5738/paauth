import pytest
import uuid
from datetime import datetime, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import status

from auth_service.main import app
from auth_service.schemas.app_client_schemas import AppClientTokenRequest, AccessTokenResponse
from auth_service.models.app_client import AppClient
from auth_service.models.role import Role
from auth_service.models.permission import Permission
from auth_service.models.role_permission import RolePermission
from auth_service.security import hash_secret, decode_m2m_access_token, generate_client_secret
from auth_service.config import settings


@pytest.mark.asyncio
async def test_token_acquisition_successful(
    async_client: AsyncClient,
    db_session_for_crud: AsyncSession
):
    """Test successful token acquisition using client credentials."""
    # 1. Create test client
    client_id = uuid.uuid4()
    client_secret = generate_client_secret()
    hashed_secret = hash_secret(client_secret)
    
    app_client = AppClient(
        id=client_id,
        client_name="Test Token Client",
        client_secret_hash=hashed_secret,
        description="Test client for token acquisition",
        allowed_callback_urls=["http://localhost:8080/callback"],
        is_active=True
    )
    
    # 2. Create test role and permission
    role = Role(name="token_test_role", description="Test role for token acquisition")
    permission = Permission(name="test:read", description="Test read permission")
    
    # 3. Add to database
    db_session_for_crud.add(app_client)
    db_session_for_crud.add(role)
    db_session_for_crud.add(permission)
    await db_session_for_crud.commit()
    
    # 4. Create role-permission association
    role_permission = RolePermission(role_id=role.id, permission_id=permission.id)
    db_session_for_crud.add(role_permission)
    await db_session_for_crud.commit()
    
    # 5. Assign role to app client using a SQL expression
    # Avoid using ORM relationship that might trigger lazy loading
    from sqlalchemy import insert
    from auth_service.models.app_client_role import AppClientRole
    
    insert_stmt = insert(AppClientRole).values(
        app_client_id=app_client.id,
        role_id=role.id
    )
    await db_session_for_crud.execute(insert_stmt)
    await db_session_for_crud.commit()
    
    # 6. Request token
    token_request = AppClientTokenRequest(
        grant_type="client_credentials",
        client_id=str(client_id),
        client_secret=client_secret
    )
    
    response = await async_client.post(
        "/auth/token",
        json=token_request.model_dump()
    )
    
    # 7. Verify response
    assert response.status_code == status.HTTP_200_OK
    response_data = response.json()
    
    # 8. Validate token structure
    token_response = AccessTokenResponse(**response_data)
    assert token_response.token_type == "Bearer"
    assert token_response.expires_in > 0
    assert token_response.access_token is not None
    
    # 9. Decode and validate token claims
    token_data = decode_m2m_access_token(token_response.access_token)
    assert token_data["sub"] == str(client_id)
    assert "token_test_role" in token_data["roles"]
    assert "test:read" in token_data["permissions"]


@pytest.mark.asyncio
async def test_token_acquisition_invalid_credentials(
    async_client: AsyncClient,
    db_session_for_crud: AsyncSession
):
    """Test token acquisition with invalid credentials."""
    # 1. Create test client
    client_id = uuid.uuid4()
    client_secret = generate_client_secret()
    wrong_secret = generate_client_secret()  # Different secret
    hashed_secret = hash_secret(client_secret)
    
    app_client = AppClient(
        id=client_id,
        client_name="Test Invalid Credentials Client",
        client_secret_hash=hashed_secret,
        description="Test client for invalid credentials",
        allowed_callback_urls=["http://localhost:8080/callback"],
        is_active=True
    )
    
    db_session_for_crud.add(app_client)
    await db_session_for_crud.commit()
    
    # 2. Request token with wrong secret
    token_request = AppClientTokenRequest(
        grant_type="client_credentials",
        client_id=str(client_id),
        client_secret=wrong_secret  # Wrong secret
    )
    
    response = await async_client.post(
        "/auth/token",
        json=token_request.model_dump()
    )
    
    # 3. Verify response
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "invalid client credentials" in response.json()["detail"].lower()
    
    # 4. Request with non-existent client ID
    non_existent_id = uuid.uuid4()
    token_request = AppClientTokenRequest(
        grant_type="client_credentials",
        client_id=str(non_existent_id),
        client_secret=client_secret
    )
    
    response = await async_client.post(
        "/auth/token",
        json=token_request.model_dump()
    )
    
    # 5. Verify response
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "invalid client credentials" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_token_acquisition_inactive_client(
    async_client: AsyncClient,
    db_session_for_crud: AsyncSession
):
    """Test token acquisition with an inactive client."""
    # 1. Create test client (inactive)
    client_id = uuid.uuid4()
    client_secret = generate_client_secret()
    hashed_secret = hash_secret(client_secret)
    
    app_client = AppClient(
        id=client_id,
        client_name="Test Inactive Client",
        client_secret_hash=hashed_secret,
        description="Test inactive client for token acquisition",
        allowed_callback_urls=["http://localhost:8080/callback"],
        is_active=False  # Inactive client
    )
    
    db_session_for_crud.add(app_client)
    await db_session_for_crud.commit()
    
    # 2. Request token
    token_request = AppClientTokenRequest(
        grant_type="client_credentials",
        client_id=str(client_id),
        client_secret=client_secret
    )
    
    response = await async_client.post(
        "/auth/token",
        json=token_request.model_dump()
    )
    
    # 3. Verify response
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "client is inactive" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_token_acquisition_invalid_grant_type(
    async_client: AsyncClient
):
    """Test token acquisition with an invalid grant type."""
    # 1. Create token request with invalid grant type
    token_request = {
        "grant_type": "password",  # Invalid grant type for this endpoint
        "client_id": str(uuid.uuid4()),
        "client_secret": "some_secret"
    }
    
    response = await async_client.post(
        "/auth/token",
        json=token_request
    )
    
    # 2. Verify response
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    response_data = response.json()
    # FastAPI validation errors have a specific format
    assert response_data["detail"][0]["loc"][1] == "grant_type"
    assert "client_credentials" in response_data["detail"][0]["msg"].lower()
