import logging
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.config import settings
from auth_service.db import get_db
from auth_service.models.app_client import AppClient
from auth_service.models.role import Role
from auth_service.models.permission import Permission
from auth_service.rate_limiting import limiter, TOKEN_LIMIT
from auth_service.schemas.app_client_schemas import AppClientTokenRequest, AccessTokenResponse
from auth_service.schemas.common_schemas import MessageResponse
from auth_service.security import verify_client_secret, create_m2m_access_token
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["Token Acquisition"],
)


@router.post(
    "/token",
    response_model=AccessTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtain an access token using client credentials",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": MessageResponse},
        status.HTTP_401_UNAUTHORIZED: {"model": MessageResponse},
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": MessageResponse},
    },
)
@limiter.limit(TOKEN_LIMIT, key_func=lambda request: request.client.host)
async def get_client_token(
    request: Request,
    token_request: AppClientTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> AccessTokenResponse:
    """
    Obtain an access token using client credentials. This endpoint implements the OAuth2 client credentials grant type.
    
    - **grant_type**: Must be 'client_credentials'.
    - **client_id**: The client ID.
    - **client_secret**: The client secret.
    
    Returns an access token that can be used to authenticate machine-to-machine API requests.
    """
    # Validate grant type
    if token_request.grant_type != "client_credentials":
        logger.warning(f"Invalid grant_type '{token_request.grant_type}' provided")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid grant_type. Only 'client_credentials' is supported.",
        )
    
    # Find the client by ID
    try:
        client_id_uuid = uuid.UUID(token_request.client_id)
    except ValueError:
        logger.warning(f"Invalid client_id format: {token_request.client_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client credentials.",
        )
    
    client = await db.get(AppClient, client_id_uuid)
    if not client:
        logger.warning(f"Client ID '{token_request.client_id}' not found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client credentials.",
        )
    
    # Check if client is active
    if not client.is_active:
        logger.warning(f"Client ID '{token_request.client_id}' is inactive")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Client is inactive.",
        )
    
    # Verify client secret
    if not verify_client_secret(token_request.client_secret, client.client_secret_hash):
        logger.warning(f"Invalid client secret for client ID '{token_request.client_id}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client credentials.",
        )
    
    # Get client's roles and permissions
    # Get app client roles
    from sqlalchemy import select
    from auth_service.models.app_client_role import AppClientRole
    
    # Query for roles associated with this client
    role_query = select(Role).join(
        AppClientRole, Role.id == AppClientRole.role_id
    ).where(AppClientRole.app_client_id == client.id)
    
    result = await db.execute(role_query)
    client_roles = result.scalars().all()
    
    # Extract role names
    role_names = [role.name for role in client_roles]
    
    # Query for permissions associated with these roles
    permissions = set()
    if client_roles:
        role_ids = [role.id for role in client_roles]
        
        # Get permissions for these roles
        from auth_service.models.role_permission import RolePermission
        
        permission_query = select(Permission).join(
            RolePermission, Permission.id == RolePermission.permission_id
        ).where(RolePermission.role_id.in_(role_ids))
        
        perm_result = await db.execute(permission_query)
        perms = perm_result.scalars().all()
        
        # Add permission names to the set
        permissions = {perm.name for perm in perms}
    
    # Create access token
    token_expiry_minutes = settings.m2m_jwt_access_token_expire_minutes
    token_expiry_seconds = token_expiry_minutes * 60  # Convert to seconds for the response
    expires_delta = timedelta(minutes=token_expiry_minutes)
    
    token = create_m2m_access_token(
        client_id=str(client.id),
        roles=role_names,
        permissions=list(permissions),
        expires_delta=expires_delta
    )
    
    logger.info(f"Generated token for client ID '{token_request.client_id}'")
    
    return AccessTokenResponse(
        access_token=token,
        token_type="Bearer",
        expires_in=token_expiry_seconds,
    )
