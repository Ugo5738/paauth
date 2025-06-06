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
    # Get the database URL
    db_url = config.get_main_option("sqlalchemy.url")
    
    # Clean the URL of pgbouncer parameter if present
    from urllib.parse import urlparse, parse_qs, urlunparse, urlencode
    import os
    
    # Parse the URL
    parsed = urlparse(db_url)
    query_params = parse_qs(parsed.query)
    
    # First check if pgbouncer parameter is in the URL
    url_has_pgbouncer = False
    if 'pgbouncer' in query_params:
        url_has_pgbouncer = query_params.pop('pgbouncer')[0].lower() == 'true'
    
    # Always rebuild URL without the pgbouncer parameter
    query_string = urlencode(query_params, doseq=True)
    clean_url = urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, query_string, parsed.fragment)
    )
    
    # Check environment variable which takes precedence
    use_pgbouncer_env = os.environ.get("USE_PGBOUNCER", "").lower()
    
    # Determine final pgbouncer setting
    use_pgbouncer = url_has_pgbouncer  # Default to URL value
    if use_pgbouncer_env in ("true", "false"):
        use_pgbouncer = (use_pgbouncer_env == "true")
        print(f"Using pgBouncer setting from environment: {use_pgbouncer}")
    else:
        print(f"Using pgBouncer setting from URL: {use_pgbouncer}")
    
    # Setup engine with connect_args for pgBouncer if needed
    engine_args = {
        "poolclass": pool.NullPool,
        "future": True,  # Ensure future=True for SQLAlchemy 2.0 features
    }
    
    if use_pgbouncer:
        print("Configuring for pgBouncer compatibility (disabling prepared statements)")
        engine_args["connect_args"] = {
            "prepared_statement_cache_size": 0,
            "statement_cache_size": 0
        }
    
    connectable = create_async_engine(clean_url, **engine_args)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
        await connection.commit()  # Ensure changes are committed

        # Verify schema after migration
        verification_passed = await verify_schema_after_migration(connection)
        if not verification_passed:
            print(
                "\n[VERIFY_MIGRATIONS] ⚠️ WARNING: Schema verification failed after migration! Some columns might be missing."
            )
            print(
                "\n[VERIFY_MIGRATIONS] This could lead to UndefinedColumn errors in your application."
            )
            print(
                "\n[VERIFY_MIGRATIONS] Consider manually checking your database schema or rolling back this migration."
            )
            # We don't raise an exception here to allow migrations to continue in production
            # but we provide a clear warning that something might be wrong

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode by wrapping the async version."""
    asyncio.run(run_migrations_online_async())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
