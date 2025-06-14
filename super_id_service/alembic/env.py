import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.pool import NullPool

# Explicitly import all models to ensure they're registered with Base.metadata
# Import Base from the correct location in super_id_service
from super_id_service.models.generated_super_id import Base, GeneratedSuperID

# Import any additional models here if they are added later

# Import service metadata to be used for migrations
target_metadata = Base.metadata

# This is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)


# Filter function to include only objects in the public schema
def include_object(object, name, type_, reflected, compare_to):
    if hasattr(object, "schema") and object.schema not in (None, "public"):
        return False
    return True


def get_url():
    """Get the database URL from settings or environment"""
    db_url = os.environ.get("SUPER_ID_SERVICE_DATABASE_URL")

    if not db_url:
        # Fall back to auth_service settings
        try:
            from super_id_service.config import settings

            db_url = settings.super_id_service_database_url
        except ImportError:
            # If settings not available, use a default connection string
            db_url = "postgresql+psycopg://postgres:postgres@localhost:5432/postgres"

    return db_url


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_schemas=True,
            # Include only the public schema for migrations
            include_object=lambda obj, name, type_, reflected, compare_to: (
                obj.schema in (None, "public") if hasattr(obj, "schema") else True
            ),
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
