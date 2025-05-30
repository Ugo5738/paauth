# auth_service/tests/conftest.py

pytest_plugins = "pytest_asyncio"

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import TIMESTAMP, Boolean, Column, String, Table, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from alembic.config import Config as AlembicConfig
# alembic.command is not directly used in the new approach
import os # To construct path to alembic.ini
from sqlalchemy.pool import NullPool
from alembic.script import ScriptDirectory
from alembic.runtime.environment import EnvironmentContext
from alembic import context as alembic_global_context # For managing global alembic context

from auth_service.config import settings
from auth_service.db import Base, get_db
from auth_service.main import app

Table(
    "users",
    Base.metadata,
    Column("id", PGUUID(as_uuid=True), primary_key=True),
    Column("email", String(255), unique=True),
    Column("phone_number", String(255), unique=True, nullable=True),
    Column("username", String(255), unique=True, nullable=True),
    Column("password_hash", String(255), nullable=True),
    Column("first_name", String(255), nullable=True),
    Column("last_name", String(255), nullable=True),
    Column("is_active", Boolean, server_default=text("true")),
    Column("is_verified", Boolean, server_default=text("false")),
    Column("last_login_at", TIMESTAMP(timezone=True), nullable=True),
    Column(
        "created_at", TIMESTAMP(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    ),
    Column(
        "updated_at", TIMESTAMP(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    ),
    schema="auth",
    extend_existing=True,
)

# Test database configuration
TEST_DATABASE_URL = settings.auth_service_database_url

# Determine the root directory of the project where alembic.ini is located
# Assuming conftest.py is in /app/tests/ and alembic.ini is in /app/
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALEMBIC_INI_PATH = os.path.join(PROJECT_ROOT, "alembic.ini")
ALEMBIC_SCRIPT_LOCATION = os.path.join(PROJECT_ROOT, "alembic")

# Helper function for alembic configuration, adapted from parts of alembic/env.py logic
def _include_object_for_conftest(object_item, name, type_, reflected, compare_to):
    if type_ == "table":
        return object_item.schema in [None, "public", "auth"]
    elif type_ == "schema":
        return name in ["auth", "public"]
    return True

def _run_alembic_upgrade_sync(connection, alembic_config: AlembicConfig):
    """Synchronously run Alembic upgrade using EnvironmentContext."""
    db_url_for_alembic = alembic_config.get_main_option('sqlalchemy.url')
    print(f"\n[CONTEST_ALEMBIC_MIGRATION] Attempting to use database URL: {db_url_for_alembic}\n")
    script = ScriptDirectory.from_config(alembic_config)

    def upgrade_ops(rev, context): # context here is the EnvironmentContext
        return script._upgrade_revs("head", rev)

    env_context = EnvironmentContext(
        config=alembic_config,
        script=script,
        fn=upgrade_ops
    )

    # Configure the environment context with connection and other parameters
    # These attributes are set on alembic_config before this function is called
    env_context.configure(
        connection=connection,
        target_metadata=alembic_config.attributes.get('target_metadata'),
        include_object=alembic_config.attributes.get('include_object'),
        include_schemas=alembic_config.attributes.get('include_schemas', True),
        compare_type=alembic_config.attributes.get('compare_type', True),
        # Add any other parameters your env.py's context.configure might use
    )

    # Run migrations within a transaction managed by the EnvironmentContext
    with env_context.begin_transaction():
        env_context.run_migrations()

@pytest_asyncio.fixture(scope="session")
async def apply_migrations_to_test_db():
    """Applies all alembic migrations to the test database asynchronously."""
    alembic_cfg = AlembicConfig(ALEMBIC_INI_PATH)
    alembic_cfg.set_main_option("script_location", ALEMBIC_SCRIPT_LOCATION)
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)

    # Pass Base.metadata and other necessary configs via attributes for env_context.configure
    alembic_cfg.attributes['target_metadata'] = Base.metadata
    alembic_cfg.attributes['include_object'] = _include_object_for_conftest
    alembic_cfg.attributes['include_schemas'] = True # As used in your env.py
    alembic_cfg.attributes['compare_type'] = True    # As used in your env.py

    # Manage global alembic context config
    original_global_alembic_config = getattr(alembic_global_context, 'config', None)
    alembic_global_context.config = alembic_cfg

    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
        future=True,
    )

    try:
        async with engine.connect() as connection:
            await connection.run_sync(_run_alembic_upgrade_sync, alembic_cfg)
            # The transaction within _run_alembic_upgrade_sync should commit itself.
            
            # Verify migrations were properly applied
            print("\n[VERIFY_MIGRATIONS] Running schema verification to ensure all migrations were properly applied...")
            
            # Inline verification logic
            try:
                # Get expected schema from models
                expected_tables = set()
                expected_columns = {}
                
                for table_name, table in Base.metadata.tables.items():
                    # Skip auth schema tables that might be managed by Supabase
                    if table_name.startswith("auth."):
                        continue
                        
                    # For tables with schema, use just the table name for comparison
                    if "." in table_name:
                        simple_name = table_name.split(".")[-1]
                    else:
                        simple_name = table_name
                        
                    expected_tables.add(simple_name)
                    expected_columns[simple_name] = set(column.name for column in table.columns)
                
                # Get actual schema from database
                actual_tables = set()
                actual_columns = {}
                
                # Get all tables in the public schema
                result = await connection.execute(
                    text("""SELECT table_name FROM information_schema.tables 
                           WHERE table_schema = 'public' AND table_type = 'BASE TABLE'""")
                )
                
                for row in result:
                    table_name = row[0]
                    actual_tables.add(table_name)
                    
                    # Get columns for this table
                    col_result = await connection.execute(
                        text("""SELECT column_name FROM information_schema.columns 
                               WHERE table_schema = 'public' AND table_name = :table_name"""),
                        {"table_name": table_name}
                    )
                    
                    actual_columns[table_name] = set(row[0] for row in col_result)
                
                # Verify tables
                missing_tables = expected_tables - actual_tables
                if missing_tables:
                    print(f"\n[VERIFY_MIGRATIONS] ❌ Missing tables in database: {missing_tables}")
                    raise RuntimeError(f"Missing tables: {missing_tables}")
                    
                # Verify columns
                schema_issues = []
                for table_name, expected_cols in expected_columns.items():
                    if table_name not in actual_columns:
                        continue  # Already reported as missing table
                        
                    actual_cols = actual_columns[table_name]
                    missing_columns = expected_cols - actual_cols
                    
                    if missing_columns:
                        schema_issues.append(
                            f"Table '{table_name}' is missing columns: {missing_columns}"
                        )
                
                if schema_issues:
                    for issue in schema_issues:
                        print(f"\n[VERIFY_MIGRATIONS] ❌ {issue}")
                    raise RuntimeError("Schema verification failed: " + "; ".join(schema_issues))
                    
                print("\n[VERIFY_MIGRATIONS] ✅ Database schema verification passed - all expected tables and columns exist.")
            except Exception as e:
                print(f"\n[VERIFY_MIGRATIONS] ❌ CRITICAL: Database schema verification failed! Migration may be incomplete.\n{str(e)}")
                print("\n[VERIFY_MIGRATIONS] This might result in UndefinedColumn errors during tests.")
                raise RuntimeError("Database schema verification failed after migrations. See logs for details.") from e

    finally:
        # Restore original global alembic config
        if original_global_alembic_config is not None:
            alembic_global_context.config = original_global_alembic_config
        elif hasattr(alembic_global_context, 'config'):
            # If it was None before but set by us (to alembic_cfg), remove it
            delattr(alembic_global_context, 'config')
        
        await engine.dispose()

@pytest_asyncio.fixture(scope="session")
async def test_engine(apply_migrations_to_test_db: None) -> AsyncGenerator[AsyncEngine, None]:
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
        pool_pre_ping=True,
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session_for_crud(
    test_engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session that properly manages transactions."""

    # Create a connection that will be used for the entire test
    connection = await test_engine.connect()

    # Start a transaction
    transaction = await connection.begin()

    # Create session bound to the connection
    async_session_maker = sessionmaker(
        bind=connection,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=True,
        autocommit=False,
    )

    session = async_session_maker()

    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()  # Rollback the transaction
        await connection.close()


@pytest_asyncio.fixture(scope="function")
async def async_client(
    db_session_for_crud: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client with database session override."""

    async def override_get_db():
        yield db_session_for_crud

    # Override the database dependency
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # Clean up override
    if get_db in app.dependency_overrides:
        del app.dependency_overrides[get_db]
