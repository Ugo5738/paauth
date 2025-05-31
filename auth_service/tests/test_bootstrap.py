import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import select

from auth_service.bootstrap import (
    bootstrap_admin_and_rbac,
    create_core_roles,
    create_core_permissions,
    assign_permissions_to_roles,
    create_admin_user,
    assign_admin_role_to_user,
    create_admin_profile
)
from auth_service.models.role import Role
from auth_service.models.permission import Permission
from auth_service.models.role_permission import RolePermission
from auth_service.models.user_role import UserRole


@pytest.mark.asyncio
async def test_create_core_roles(db_session_for_crud):
    # Test creating core roles
    role_ids = await create_core_roles(db_session_for_crud)
    
    # Verify that we have the expected roles
    assert "admin" in role_ids
    assert "user" in role_ids
    assert "service" in role_ids
    
    # Verify roles are in the database
    result = await db_session_for_crud.execute(select(Role))
    roles = result.scalars().all()
    assert len(roles) >= 3  # At least the core roles should exist
    
    # Verify idempotency - running again shouldn't create duplicates
    role_ids_2 = await create_core_roles(db_session_for_crud)
    result = await db_session_for_crud.execute(select(Role))
    roles_after = result.scalars().all()
    assert len(roles) == len(roles_after)  # Should be the same count


@pytest.mark.asyncio
async def test_create_core_permissions(db_session_for_crud):
    # Test creating core permissions
    perm_ids = await create_core_permissions(db_session_for_crud)
    
    # Verify that we have the expected permissions
    assert "users:read" in perm_ids
    assert "users:write" in perm_ids
    assert "role:admin_manage" in perm_ids
    
    # Verify permissions are in the database
    result = await db_session_for_crud.execute(select(Permission))
    perms = result.scalars().all()
    assert len(perms) >= 7  # At least the core permissions should exist


@pytest.mark.asyncio
async def test_assign_permissions_to_roles(db_session_for_crud):
    # First create roles and permissions
    role_ids = await create_core_roles(db_session_for_crud)
    perm_ids = await create_core_permissions(db_session_for_crud)
    
    # Test assigning permissions to roles
    await assign_permissions_to_roles(db_session_for_crud, role_ids, perm_ids)
    
    # Verify admin role has all permissions
    admin_role_id = role_ids["admin"]
    result = await db_session_for_crud.execute(
        select(RolePermission).where(RolePermission.role_id == admin_role_id)
    )
    admin_perms = result.scalars().all()
    assert len(admin_perms) == 7  # Admin should have all 7 core permissions
    
    # Verify user role has only users:read permission
    user_role_id = role_ids["user"]
    result = await db_session_for_crud.execute(
        select(RolePermission).where(RolePermission.role_id == user_role_id)
    )
    user_perms = result.scalars().all()
    assert len(user_perms) == 1  # User should have only 1 permission


@pytest.mark.asyncio
async def test_create_admin_user():
    # Mock Supabase client
    mock_supabase = AsyncMock()
    mock_user = MagicMock()
    mock_user.id = str(uuid.uuid4())
    mock_user.email = "admin@example.com"
    mock_user.aud = "authenticated"
    mock_user.role = "authenticated"
    mock_user.phone = None  # Fix: Set phone to None instead of letting it be a MagicMock
    mock_user.email_confirmed_at = "2023-01-01T00:00:00Z"  # Add this required field
    mock_user.phone_confirmed_at = None  # Add this required field
    mock_user.last_sign_in_at = None  # Add this required field
    mock_user.app_metadata = {}
    mock_user.user_metadata = {}
    mock_user.identities = []
    mock_user.created_at = "2023-01-01T00:00:00Z"
    mock_user.updated_at = "2023-01-01T00:00:00Z"
    
    # Mock admin.create_user response
    mock_response = MagicMock()
    mock_response.user = mock_user
    mock_supabase.auth.admin.create_user.return_value = mock_response
    
    # Mock admin.list_users response to simulate no existing users
    mock_list_response = MagicMock()
    mock_list_response.users = []
    mock_supabase.auth.admin.list_users.return_value = mock_list_response
    
    # Test creating admin user
    admin_user = await create_admin_user(
        mock_supabase, "admin@example.com", "password123"
    )
    
    # Verify admin user was created
    assert admin_user is not None
    assert admin_user.email == "admin@example.com"
    assert str(admin_user.id) == mock_user.id  # Compare string representations
    
    # Verify Supabase client was called correctly
    mock_supabase.auth.admin.create_user.assert_called_once()
    create_user_args = mock_supabase.auth.admin.create_user.call_args[0][0]
    assert create_user_args["email"] == "admin@example.com"
    assert create_user_args["password"] == "password123"
    assert create_user_args["email_confirm"] is True


@pytest.mark.asyncio
async def test_bootstrap_admin_and_rbac():
    # Mock dependencies
    mock_db = AsyncMock()
    mock_supabase = AsyncMock()
    
    test_admin_email = "admin@example.com"
    test_admin_password = "password123"
    
    # Mock successful execution of all sub-functions
    with patch('auth_service.bootstrap.create_core_roles') as mock_create_roles, \
         patch('auth_service.bootstrap.create_core_permissions') as mock_create_perms, \
         patch('auth_service.bootstrap.assign_permissions_to_roles') as mock_assign, \
         patch('auth_service.bootstrap.create_admin_user') as mock_create_admin, \
         patch('auth_service.bootstrap.create_admin_profile') as mock_create_profile, \
         patch('auth_service.bootstrap.assign_admin_role_to_user') as mock_assign_role, \
         patch('auth_service.bootstrap.settings.initial_admin_email', test_admin_email), \
         patch('auth_service.bootstrap.settings.initial_admin_password', test_admin_password):
        
        # Configure mocks
        mock_create_roles.return_value = {"admin": uuid.uuid4(), "user": uuid.uuid4()}
        mock_create_perms.return_value = {"users:read": uuid.uuid4()}
        mock_assign.return_value = None
        
        mock_user = MagicMock()
        mock_user.id = str(uuid.uuid4())
        mock_user.email = "admin@example.com"
        mock_create_admin.return_value = mock_user
        
        mock_create_profile.return_value = True
        mock_assign_role.return_value = True
        
        # Settings are now directly patched via the mock decorators
        
        # Test bootstrap process
        success = await bootstrap_admin_and_rbac(mock_db, mock_supabase)
        
        # Verify bootstrap was successful
        assert success is True
        
        # Verify all functions were called
        mock_create_roles.assert_called_once()
        mock_create_perms.assert_called_once()
        mock_assign.assert_called_once()
        mock_create_admin.assert_called_once_with(
            mock_supabase, "admin@example.com", "password123"
        )
        mock_create_profile.assert_called_once()
        mock_assign_role.assert_called_once()
