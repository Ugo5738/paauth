import logging
import uuid
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from supabase._async.client import AsyncClient
from gotrue.errors import AuthApiError

from auth_service.config import settings
from auth_service.models.role import Role
from auth_service.models.permission import Permission
from auth_service.models.role_permission import RolePermission
from auth_service.models.user_role import UserRole
from auth_service.schemas.user_schemas import ProfileCreate, SupabaseUser
from auth_service.routers.user_auth_routes import create_profile_in_db

logger = logging.getLogger(__name__)

# Core roles to be created during bootstrapping
CORE_ROLES = [
    {"name": "admin", "description": "Full system access"},
    {"name": "user", "description": "Basic authenticated user access"},
    {"name": "service", "description": "For machine-to-machine communication"}
]

# Core permissions to be created during bootstrapping
CORE_PERMISSIONS = [
    {"name": "users:read", "description": "View user information"},
    {"name": "users:write", "description": "Create/update user information"},
    {"name": "roles:read", "description": "View roles"},
    {"name": "roles:write", "description": "Create/update roles"},
    {"name": "permissions:read", "description": "View permissions"},
    {"name": "permissions:write", "description": "Create/update permissions"},
    {"name": "role:admin_manage", "description": "Special permission for admin operations"}
]

# Role-permission mapping for initial setup
ROLE_PERMISSIONS_MAP = {
    "admin": ["users:read", "users:write", "roles:read", "roles:write", 
              "permissions:read", "permissions:write", "role:admin_manage"],
    "user": ["users:read"],  # Users can only view their own profile
    "service": []  # Empty by default, to be configured based on specific service needs
}


async def create_core_roles(db: AsyncSession) -> Dict[str, uuid.UUID]:
    """Create the core roles if they don't exist yet."""
    role_ids = {}
    
    for role_data in CORE_ROLES:
        # Check if role already exists
        stmt = select(Role).where(Role.name == role_data["name"])
        result = await db.execute(stmt)
        existing_role = result.scalars().first()
        
        if existing_role:
            logger.info(f"Role '{role_data['name']}' already exists")
            role_ids[role_data["name"]] = existing_role.id
        else:
            # Create new role
            new_role = Role(
                id=uuid.uuid4(),
                name=role_data["name"],
                description=role_data["description"]
            )
            db.add(new_role)
            await db.flush()  # Flush to get the ID
            role_ids[role_data["name"]] = new_role.id
            logger.info(f"Created new role: {role_data['name']}")
    
    await db.commit()
    return role_ids


async def create_core_permissions(db: AsyncSession) -> Dict[str, uuid.UUID]:
    """Create the core permissions if they don't exist yet."""
    permission_ids = {}
    
    for perm_data in CORE_PERMISSIONS:
        # Check if permission already exists
        stmt = select(Permission).where(Permission.name == perm_data["name"])
        result = await db.execute(stmt)
        existing_perm = result.scalars().first()
        
        if existing_perm:
            logger.info(f"Permission '{perm_data['name']}' already exists")
            permission_ids[perm_data["name"]] = existing_perm.id
        else:
            # Create new permission
            new_perm = Permission(
                id=uuid.uuid4(),
                name=perm_data["name"],
                description=perm_data["description"]
            )
            db.add(new_perm)
            await db.flush()  # Flush to get the ID
            permission_ids[perm_data["name"]] = new_perm.id
            logger.info(f"Created new permission: {perm_data['name']}")
    
    await db.commit()
    return permission_ids


async def assign_permissions_to_roles(
    db: AsyncSession, 
    role_ids: Dict[str, uuid.UUID], 
    permission_ids: Dict[str, uuid.UUID]
) -> None:
    """Assign permissions to roles according to the mapping."""
    for role_name, permission_names in ROLE_PERMISSIONS_MAP.items():
        if role_name not in role_ids:
            logger.warning(f"Role '{role_name}' not found, skipping permission assignment")
            continue
            
        role_id = role_ids[role_name]
        
        for perm_name in permission_names:
            if perm_name not in permission_ids:
                logger.warning(f"Permission '{perm_name}' not found, skipping assignment to role '{role_name}'")
                continue
                
            perm_id = permission_ids[perm_name]
            
            # Check if assignment already exists
            stmt = select(RolePermission).where(
                RolePermission.role_id == role_id,
                RolePermission.permission_id == perm_id
            )
            result = await db.execute(stmt)
            existing_assignment = result.scalars().first()
            
            if existing_assignment:
                logger.info(f"Permission '{perm_name}' already assigned to role '{role_name}'")
                continue
                
            # Create new assignment
            new_assignment = RolePermission(
                role_id=role_id,
                permission_id=perm_id
            )
            db.add(new_assignment)
            logger.info(f"Assigned permission '{perm_name}' to role '{role_name}'")
    
    await db.commit()


async def create_admin_user(
    supabase: AsyncClient, 
    email: str, 
    password: str
) -> Optional[SupabaseUser]:
    """Create an admin user in Supabase if one doesn't exist."""
    try:
        # Check if admin email already exists
        user_response = await supabase.auth.admin.list_users()
        users = user_response.users
        
        for user in users:
            if user.email == email:
                logger.info(f"Admin user with email '{email}' already exists")
                # Return the existing user
                return SupabaseUser(
                    id=user.id,
                    email=user.email,
                    aud=user.aud or "",
                    role=user.role,
                    phone=user.phone,
                    email_confirmed_at=user.email_confirmed_at,
                    phone_confirmed_at=user.phone_confirmed_at,
                    confirmed_at=getattr(
                        user,
                        "confirmed_at",
                        user.email_confirmed_at or user.phone_confirmed_at,
                    ),
                    last_sign_in_at=user.last_sign_in_at,
                    app_metadata=user.app_metadata or {},
                    user_metadata=user.user_metadata or {},
                    identities=user.identities or [],
                    created_at=user.created_at,
                    updated_at=user.updated_at,
                )
        
        # Create a new admin user
        signup_response = await supabase.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,  # Auto-confirm email
            "user_metadata": {"roles": ["admin"]}
        })
        
        if not signup_response.user:
            logger.error("Failed to create admin user - no user returned")
            return None
            
        # Create a SupabaseUser object
        admin_user = SupabaseUser(
            id=signup_response.user.id,
            email=signup_response.user.email,
            aud=signup_response.user.aud or "",
            role=signup_response.user.role,
            phone=signup_response.user.phone,
            email_confirmed_at=signup_response.user.email_confirmed_at,
            phone_confirmed_at=signup_response.user.phone_confirmed_at,
            confirmed_at=getattr(
                signup_response.user,
                "confirmed_at",
                signup_response.user.email_confirmed_at or signup_response.user.phone_confirmed_at,
            ),
            last_sign_in_at=signup_response.user.last_sign_in_at,
            app_metadata=signup_response.user.app_metadata or {},
            user_metadata=signup_response.user.user_metadata or {},
            identities=signup_response.user.identities or [],
            created_at=signup_response.user.created_at,
            updated_at=signup_response.user.updated_at,
        )
        
        logger.info(f"Created new admin user with email '{email}'")
        return admin_user
        
    except AuthApiError as e:
        logger.error(f"Supabase API error creating admin user: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error creating admin user: {e}")
        return None


async def assign_admin_role_to_user(
    db: AsyncSession, 
    user_id: str, 
    admin_role_id: uuid.UUID
) -> bool:
    """Assign the admin role to a user."""
    try:
        # Check if assignment already exists
        stmt = select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.role_id == admin_role_id
        )
        result = await db.execute(stmt)
        existing_assignment = result.scalars().first()
        
        if existing_assignment:
            logger.info(f"Admin role already assigned to user '{user_id}'")
            return True
            
        # Create new assignment
        new_assignment = UserRole(
            user_id=user_id,
            role_id=admin_role_id
        )
        db.add(new_assignment)
        await db.commit()
        
        logger.info(f"Assigned admin role to user '{user_id}'")
        return True
        
    except Exception as e:
        logger.error(f"Error assigning admin role to user '{user_id}': {e}")
        await db.rollback()
        return False


async def create_admin_profile(
    db: AsyncSession, 
    admin_user: SupabaseUser
) -> bool:
    """Create a profile for the admin user."""
    try:
        # Check if profile already exists
        stmt = select(UserRole).where(UserRole.user_id == admin_user.id)
        result = await db.execute(stmt)
        existing_profile = result.scalars().first()
        
        if existing_profile:
            logger.info(f"Profile already exists for admin user '{admin_user.id}'")
            return True
            
        # Create profile
        profile_data = ProfileCreate(
            user_id=admin_user.id,
            email=admin_user.email,
            username=f"admin_{admin_user.id[:8]}",  # Create a default username
            first_name="Admin",
            last_name="User"
        )
        
        await create_profile_in_db(db, profile_data, admin_user.id)
        logger.info(f"Created profile for admin user '{admin_user.id}'")
        return True
        
    except Exception as e:
        logger.error(f"Error creating profile for admin user '{admin_user.id}': {e}")
        return False


async def bootstrap_admin_and_rbac(
    db: AsyncSession, 
    supabase: AsyncClient
) -> bool:
    """Main bootstrapping function to setup initial admin and RBAC components."""
    try:
        logger.info("Starting admin and RBAC bootstrapping process")
        
        # 1. Create core roles
        role_ids = await create_core_roles(db)
        
        # 2. Create core permissions
        permission_ids = await create_core_permissions(db)
        
        # 3. Assign permissions to roles
        await assign_permissions_to_roles(db, role_ids, permission_ids)
        
        # 4. Create admin user if environment variables are set
        if settings.initial_admin_email and settings.initial_admin_password:
            admin_user = await create_admin_user(
                supabase, 
                settings.initial_admin_email, 
                settings.initial_admin_password
            )
            
            if admin_user:
                # 5. Create admin profile
                await create_admin_profile(db, admin_user)
                
                # 6. Assign admin role to user
                if "admin" in role_ids:
                    await assign_admin_role_to_user(db, admin_user.id, role_ids["admin"])
                else:
                    logger.error("Admin role not found, could not assign to user")
            else:
                logger.warning("Admin user creation failed or was skipped")
        else:
            logger.info("Admin user creation skipped (initial_admin_email or initial_admin_password not set)")
        
        logger.info("Admin and RBAC bootstrapping completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error during admin and RBAC bootstrapping: {e}")
        return False


# Entry point for CLI command
async def run_bootstrap(db: AsyncSession, supabase: AsyncClient):
    """Run the bootstrapping process. Can be called from CLI or during startup."""
    success = await bootstrap_admin_and_rbac(db, supabase)
    if success:
        logger.info("Bootstrap process completed successfully")
    else:
        logger.error("Bootstrap process failed")
    return success
