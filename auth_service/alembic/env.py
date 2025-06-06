import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import TIMESTAMP as SATimestamp
from sqlalchemy import Boolean as SABoolean
from sqlalchemy import Column
from sqlalchemy import (
    String as SAString,  # Use SAString etc. to avoid conflict if String is imported from elsewhere
)
from sqlalchemy import Table, engine_from_config, pool
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import create_async_engine

from auth_service.config import settings
from auth_service.db import Base
from auth_service.models import AppClient  # Ensure AppClient is also imported
from auth_service.models import (
    AppClientRefreshToken,  # Ensure AppClientRefreshToken is also imported
)
from auth_service.models import AppClientRole  # Ensure AppClientRole is also imported
from auth_service.models import Permission  # Ensure Permission is also imported
from auth_service.models import Profile  # Ensure models are imported for autogenerate
from auth_service.models import Role  # Ensure Role is also imported
from auth_service.models import RolePermission  # Ensure RolePermission is also imported
from auth_service.models import UserRole  # Ensure UserRole is also imported

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
config.set_main_option(
    "sqlalchemy.url", settings.auth_service_database_url
)  # Earlier disabled for tests; conftest.py handles this.

# Explicitly define or ensure auth.users table is part of Base.metadata
# This helps autogenerate find it, especially if it's managed by Supabase but referenced by local models.
Table(
    "users",
    Base.metadata,
    Column("id", PGUUID(as_uuid=True), primary_key=True),
    Column("email", SAString(255), unique=True),
    Column("phone_number", SAString(255), unique=True, nullable=True),
    Column("username", SAString(255), unique=True, nullable=True),
    Column("password_hash", SAString(255), nullable=True),
    Column("first_name", SAString(255), nullable=True),
    Column("last_name", SAString(255), nullable=True),
    Column("is_active", SABoolean, server_default=sa_text("true")),
    Column("is_verified", SABoolean, server_default=sa_text("false")),
    Column("last_login_at", SATimestamp(timezone=True), nullable=True),
    Column(
        "created_at",
        SATimestamp(timezone=True),
        server_default=sa_text("CURRENT_TIMESTAMP"),
    ),
    Column(
        "updated_at",
        SATimestamp(timezone=True),
        server_default=sa_text("CURRENT_TIMESTAMP"),
    ),
    schema="auth",
    extend_existing=True,
)

target_metadata = Base.metadata


# Function to control which objects are considered by autogenerate
def include_object(object, name, type_, reflected, compare_to):
    # Only manage objects in the 'public' schema (or your custom app schema if you used one)
    # None schema is often the default 'public' schema in PostgreSQL.
    if type_ == "table":
        if object.schema not in [
            None,
            "public",
        ]:  # Adjust "public" if your tables are in a different custom schema
            return False
    elif type_ == "schema":
        if name not in [
            None,
            "public",
        ]:  # Adjust "public" if your tables are in a different custom schema
            return False
    # By default, allow other types unless explicitly excluded
    return True


# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    print(
        f"\n[ENV.PY_DO_RUN_MIGRATIONS] Entered function. Connection: {connection}\n"
    )  # Added print
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,  # Added to handle multi-schema objects like auth.users
        compare_type=True,  # Recommended for more accurate type comparison
        include_object=include_object,  # Explicitly guide autogenerate
    )
    print(
        f"\n[ENV.PY_DO_RUN_MIGRATIONS] Context configured. About to begin transaction and run migrations.\n"
    )  # Added print
    with context.begin_transaction():
        print(
            f"\n[ENV.PY_DO_RUN_MIGRATIONS] Transaction begun. Calling context.run_migrations().\n"
        )  # Added print
        context.run_migrations()
        print(
            f"\n[ENV.PY_DO_RUN_MIGRATIONS] context.run_migrations() completed.\n"
        )  # Added print


async def verify_schema_after_migration(connection) -> None:
    """Verify database schema after migrations to ensure they were applied correctly."""
    try:
        print(
            "\n[VERIFY_MIGRATIONS] Running schema verification to ensure all migrations were properly applied..."
        )

        # Get expected schema from models
        tables = set()
        columns = {}

        for table_name, table in target_metadata.tables.items():
            # Skip auth schema tables that might be managed by Supabase
            if table_name.startswith("auth."):
                continue

            # For tables with schema, use just the table name for comparison
            if "." in table_name:
                simple_name = table_name.split(".")[-1]
            else:
                simple_name = table_name

            tables.add(simple_name)
            columns[simple_name] = set(column.name for column in table.columns)

        # Get actual schema from database
        actual_tables = set()
        actual_columns = {}

        # Get all tables in the public schema
        result = await connection.execute(
            sa_text(
                """SELECT table_name FROM information_schema.tables 
                   WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"""
            )
        )

        for row in result:
            table_name = row[0]
            actual_tables.add(table_name)

            # Get columns for this table
            col_result = await connection.execute(
                sa_text(
                    """SELECT column_name FROM information_schema.columns 
                       WHERE table_schema = 'public' AND table_name = :table_name"""
                ),
                {"table_name": table_name},
            )

            actual_columns[table_name] = set(row[0] for row in col_result)

        # Verify tables
        missing_tables = tables - actual_tables
        if missing_tables:
            print(
                f"\n[VERIFY_MIGRATIONS] ❌ Missing tables in database: {missing_tables}"
            )
            return False

        # Verify columns
        schema_issues = []
        for table_name, expected_cols in columns.items():
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
            return False

        print(
            "\n[VERIFY_MIGRATIONS] ✅ Database schema verification passed - all expected tables and columns exist"
        )
        return True

    except Exception as e:
        print(f"\n[VERIFY_MIGRATIONS] ❌ Error verifying migrations: {e}")
        return False


async def run_migrations_online_async() -> None:
    """Run migrations in 'online' mode asynchronously."""
    # Import necessary modules
    import asyncio
    import os
    import time
    from urllib.parse import urlparse, parse_qs, urlunparse, urlencode
    from sqlalchemy.exc import SQLAlchemyError, OperationalError, TimeoutError
    from sqlalchemy.sql import text
    import logging
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('alembic.migrations')
    
    # Get the database URL
    db_url = config.get_main_option("sqlalchemy.url")
    
    # Parse the URL to understand its components and clean pgbouncer parameter
    parsed = urlparse(db_url)
    query_params = parse_qs(parsed.query)
    
    # Always remove pgbouncer parameter from URL, we'll control it separately
    url_has_pgbouncer = False
    if 'pgbouncer' in query_params:
        url_has_pgbouncer = query_params.pop('pgbouncer')[0].lower() == 'true'
        
    # Remove any pgbouncer-incompatible parameters
    for incompatible_param in ['prepared_statement_cache_size', 'statement_cache_size', 'keepalives', 
                                'keepalives_idle', 'keepalives_interval', 'keepalives_count']:
        if incompatible_param in query_params:
            del query_params[incompatible_param]
    
    # Rebuild clean URL without pgbouncer parameter
    query_string = urlencode(query_params, doseq=True)
    clean_url = urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, query_string, parsed.fragment)
    )
    
    # Check if environment variable is set, which takes precedence
    use_pgbouncer_env = os.environ.get("USE_PGBOUNCER", "").lower()
    
    # Determine final pgbouncer setting
    use_pgbouncer = url_has_pgbouncer  # Default to URL value first
    
    # Environment variable overrides URL parameter when set explicitly
    if use_pgbouncer_env in ("true", "false"):
        use_pgbouncer = (use_pgbouncer_env == "true")
        logger.info(f"Using pgBouncer setting from environment: {use_pgbouncer}")
    else:
        logger.info(f"Using pgBouncer setting from URL: {use_pgbouncer}")
    
    # For migrations, we'll enforce no pgBouncer mode due to compatibility issues
    if use_pgbouncer:
        logger.warning("⚠️ pgBouncer mode is set to true, but will be disabled for migrations to prevent issues")
        logger.warning("⚠️ Your app will still run with pgBouncer enabled as per your configuration")
        use_pgbouncer = False
        
    logger.info(f"Final pgBouncer setting for migrations: {use_pgbouncer}")
    
    # Configure connection parameters with timeouts from environment or defaults
    # Allow override via environment variables for different deployment scenarios
    connect_timeout = int(os.environ.get("DB_CONNECT_TIMEOUT", 60))  # Increased default to 60s
    command_timeout = int(os.environ.get("DB_COMMAND_TIMEOUT", 60))   # Increased default to 60s
    statement_timeout = int(os.environ.get("DB_STATEMENT_TIMEOUT", 0)) # 0 = no timeout (for long migrations)
    idle_in_transaction_timeout = int(os.environ.get("DB_IDLE_TIMEOUT", 180)) # 3 minutes
    
    logger.info(f"Using database timeouts: connect={connect_timeout}s, command={command_timeout}s")
    
    # Configure connection parameters with extended timeouts for migrations
    connect_args = {
        "timeout": connect_timeout,           # Connection establishment timeout
        "command_timeout": command_timeout,  # Individual command timeout
        "server_settings": {
            "application_name": "paauth_alembic_migrations",
            "default_transaction_isolation": "read committed",
            "statement_timeout": str(statement_timeout * 1000),  # Convert to ms
            "idle_in_transaction_session_timeout": str(idle_in_transaction_timeout * 1000),  # Convert to ms
        }
    }
    
    # Engine arguments with NullPool to prevent connection pooling during migrations
    engine_args = {
        "poolclass": pool.NullPool,
        "future": True,  # Ensure future=True for SQLAlchemy 2.0 features
        "echo": True,    # Log SQL for debugging
        "connect_args": connect_args
    }
    
    # Add pgBouncer compatibility settings if needed
    if use_pgbouncer:
        logger.info("Configuring for pgBouncer compatibility (disabling prepared statements)")
        # These settings are critical for pgBouncer compatibility
        connect_args["prepared_statement_cache_size"] = 0
        connect_args["statement_cache_size"] = 0
    
    # Log connection info for debugging
    parsed_for_log = urlparse(clean_url)
    host_part = f"{parsed_for_log.hostname}:{parsed_for_log.port}"
    logger.info(f"Connecting to database: {host_part}{parsed_for_log.path} (pgBouncer mode: {use_pgbouncer})")
    
    # Create the async engine with our settings
    try:
        logger.info("Creating database engine...")
        connectable = create_async_engine(clean_url, **engine_args)
        
        # Define retry parameters
        MAX_RETRIES = 5
        INITIAL_RETRY_DELAY = 1.5  # seconds
        
        # Implement retry logic for connection
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(f"Connection attempt {attempt}/{MAX_RETRIES}...")
                
                # Try to connect with a timeout
                async with asyncio.timeout(30):  # 30 second overall timeout for each attempt
                    async with connectable.connect() as connection:
                        logger.info("Database connection established successfully")
                        
                        # Test the connection with a simple query
                        await connection.execute(text("SELECT 1"))
                        logger.info("Connection test passed")
                        
                        # Run migrations inside this connection
                        logger.info("Running migrations...")
                        await connection.run_sync(do_run_migrations)
                        await connection.commit()  # Ensure changes are committed
                        logger.info("Migrations completed successfully")

                        # Verify schema after migration
                        verification_passed = await verify_schema_after_migration(connection)
                        if not verification_passed:
                            logger.warning(
                                "\n[VERIFY_MIGRATIONS] ⚠️ WARNING: Schema verification failed after migration! "
                                "Some columns might be missing."
                            )
                            logger.warning(
                                "\n[VERIFY_MIGRATIONS] This could lead to UndefinedColumn errors in your application."
                            )
                            logger.warning(
                                "\n[VERIFY_MIGRATIONS] Consider manually checking your database schema or "
                                "rolling back this migration."
                            )
                        
                        # If we got here, everything worked
                        logger.info("All migration operations completed successfully")
                        break
                        
            except (SQLAlchemyError, TimeoutError, asyncio.TimeoutError) as e:
                # Connection failed
                logger.error(f"Connection attempt {attempt} failed: {e.__class__.__name__}: {str(e)}")
                
                # Check if we should retry
                if attempt < MAX_RETRIES:
                    retry_delay = INITIAL_RETRY_DELAY * (2 ** (attempt - 1))  # Exponential backoff
                    logger.info(f"Retrying in {retry_delay:.2f} seconds...")
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(f"All {MAX_RETRIES} connection attempts failed. Cannot run migrations.")
                    raise RuntimeError(f"Failed to connect to database after {MAX_RETRIES} attempts") from e
        
        # Proper cleanup
        await connectable.dispose()
        logger.info("Database connection closed")
        
    except Exception as e:
        logger.error(f"Migration failed: {e.__class__.__name__}: {str(e)}", exc_info=True)
        # Try to clean up if possible
        try:
            await connectable.dispose()
        except:
            pass
        raise


def run_migrations_online() -> None:
    """Run migrations in 'online' mode by wrapping the async version."""
    asyncio.run(run_migrations_online_async())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
