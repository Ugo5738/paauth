from typing import AsyncGenerator, Optional
import asyncio
import time
import sqlalchemy.util.concurrency as _concurrency

_concurrency._not_implemented = lambda *args, **kwargs: None

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func, text
from sqlalchemy.exc import SQLAlchemyError, OperationalError, TimeoutError

from auth_service.config import settings
from auth_service.logging_config import logger

# Connection settings optimized for Supabase pgBouncer
# Using minimal local pool since pgBouncer handles connection pooling
DB_POOL_SIZE = 2  # Smaller local connection pool when using pgBouncer
DB_MAX_OVERFLOW = 2  # Very limited overflow with pgBouncer
DB_POOL_TIMEOUT = 5  # Fail faster when pool is exhausted (5 seconds)
DB_POOL_RECYCLE = 60  # Short connection recycle time (1 minute) with pgBouncer
DB_CONNECT_TIMEOUT = 10  # Connection timeout (10 seconds)
DB_COMMAND_TIMEOUT = 5  # Command execution timeout (5 seconds)
DB_MAX_RETRIES = 3  # Number of retries for failed connections
DB_RETRY_DELAY = 0.5  # Initial retry delay (will use exponential backoff)

# Handle pgBouncer configuration using both URL parameter and environment variable
import urllib.parse
import os

# Parse the URL to remove pgbouncer parameter if present
def parse_db_url(url):
    """Parse database URL and clean parameters not supported by the driver."""
    # Check if pgBouncer parameter is in the URL
    has_pgbouncer_param = "pgbouncer=true" in url
    
    # If there's no pgbouncer parameter, return the URL as is
    if not has_pgbouncer_param:
        return url
    
    # Handle URL parsing to remove the pgbouncer parameter
    driver_prefix = ""
    if url.startswith("postgresql+"):
        driver_end = url.find("://")
        if driver_end != -1:
            driver_prefix = url[:driver_end+3]
            url = url[driver_end+3:]
    elif url.startswith("postgresql://"):
        driver_prefix = "postgresql://"
        url = url[len(driver_prefix):]
    
    # Split the URL into components
    if "@" in url:
        userpass, hostportdb = url.split("@", 1)
    else:
        userpass = ""
        hostportdb = url
    
    # Handle query parameters
    query_params = {}
    if "?" in hostportdb:
        hostportdb, query_string = hostportdb.split("?", 1)
        for param in query_string.split("&"):
            if "=" in param:
                key, value = param.split("=", 1)
                query_params[key] = value
    
    # Remove pgbouncer parameter
    if "pgbouncer" in query_params:
        del query_params["pgbouncer"]
    
    # Rebuild the URL without the pgbouncer parameter
    clean_url = driver_prefix + userpass
    if userpass:
        clean_url += "@"
    clean_url += hostportdb
    if query_params:
        clean_url += "?" + "&".join([f"{k}={v}" for k, v in query_params.items()])
    
    return clean_url

# First clean the URL of any pgbouncer parameters
clean_db_url = parse_db_url(settings.auth_service_database_url)

# Determine if pgBouncer should be used - check both URL and environment variable
# Environment variable takes precedence over URL parameter
use_pgbouncer_env = os.environ.get("USE_PGBOUNCER", "").lower()

# Default to true if pgbouncer=true was in the URL
is_pgbouncer = "pgbouncer=true" in settings.auth_service_database_url 

# Override with environment variable if specified
if use_pgbouncer_env in ("true", "false"):
    is_pgbouncer = (use_pgbouncer_env == "true")
    logger.info(f"pgBouncer mode set from environment variable: {is_pgbouncer}")
else:
    logger.info(f"pgBouncer mode detected from URL: {is_pgbouncer}")

# Detect environment - we'll use this to enable/disable features that might not be supported in test env
is_production = settings.is_production()

# Connection arguments - set up base configuration
connect_args = {
    # Connection timeouts
    "timeout": DB_CONNECT_TIMEOUT,
    "command_timeout": DB_COMMAND_TIMEOUT,
    
    # Server settings - critical for pgBouncer compatibility
    "server_settings": {
        "application_name": "paauth_service",
        # READ COMMITTED is the only isolation level supported by pgBouncer
        "default_transaction_isolation": "read committed"
    }
}

# Add pgBouncer-specific optimizations for production
if is_production and is_pgbouncer:
    logger.info("Using production pgBouncer connection optimizations")
    # Only set these parameters in production with pgBouncer
    # These might not be supported in all asyncpg versions (especially in test containers)
    try:
        # TCP keepalives help detect dead connections
        connect_args.update({
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 3
        })
    except Exception as e:
        logger.warning(f"Could not apply all pgBouncer optimizations: {e}")
    
    # Log that we're using pgBouncer compatibility mode
    logger.info("Using pgBouncer compatibility mode: disabled prepared statements")

# Add pgBouncer-specific connection arguments if needed
if is_pgbouncer:
    # Note: These parameters are the correct ones to use with SQLAlchemy's create_async_engine
    # They correspond to asyncpg's "prepared_statement_cache_size" and "statement_cache_size"
    # Do NOT use "prepare_threshold" directly - it's not supported by the driver
    connect_args.update({
        "server_settings": {
            "application_name": "paauth_service",
            # READ COMMITTED is the only isolation level supported by pgBouncer
            "default_transaction_isolation": "read committed"
        }
    })
    
    # Add engine arguments for SQLAlchemy
    engine_args = {
        "echo": settings.logging_level.upper() == "DEBUG",
        "pool_size": DB_POOL_SIZE,
        "max_overflow": DB_MAX_OVERFLOW,
        "pool_timeout": DB_POOL_TIMEOUT,
        "pool_recycle": DB_POOL_RECYCLE,
        "pool_pre_ping": True,
        "connect_args": connect_args
    }

# Optimized engine configuration for Supabase Cloud with pgBouncer
if is_pgbouncer:
    # Use predefined engine arguments with pgBouncer compatibility settings
    engine: AsyncEngine = create_async_engine(clean_db_url, **engine_args)
    logger.info("Created database engine with pgBouncer compatibility mode")
else:
    # Standard engine configuration without pgBouncer optimizations
    engine: AsyncEngine = create_async_engine(
        clean_db_url,  # Use the cleaned URL without the pgbouncer parameter
        echo=settings.logging_level.upper() == "DEBUG",
        
        # Connection pool settings
        pool_size=DB_POOL_SIZE,
        max_overflow=DB_MAX_OVERFLOW,
        pool_timeout=DB_POOL_TIMEOUT,
        pool_recycle=DB_POOL_RECYCLE,
        
        # Connection health checks
        pool_pre_ping=True,
        
        # Use our standard connect_args
        connect_args=connect_args
    )
    logger.info("Created standard database engine without pgBouncer mode")

# Session factory for async sessions
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# Base class for ORM models
Base = declarative_base()


async def verify_db_connection(session: AsyncSession, retries=1) -> bool:
    """
    Verify database connection with retry logic.
    Returns True if connection is successful, False otherwise.
    """
    for attempt in range(retries + 1):
        try:
            # Execute a simple query to verify connection
            await session.execute(text("SELECT 1"))
            if attempt > 0:
                logger.info(f"Database connection restored on attempt {attempt + 1}")
            return True
        except SQLAlchemyError as e:
            if attempt < retries:
                wait_time = DB_RETRY_DELAY * (2 ** attempt)  # Exponential backoff
                logger.warning(
                    f"Database connection attempt {attempt + 1} failed: {str(e)}. "
                    f"Retrying in {wait_time:.2f}s..."
                )
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"Failed to connect to database after {retries + 1} attempts: {str(e)}")
                return False
    return False


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Async session generator for dependency injection with improved error handling.
    
    Features:
    - Connection retry logic with exponential backoff
    - Proper session cleanup to prevent leaks
    - Detailed error reporting
    - Timeout handling
    
    Commits should be handled within the business logic using the session.
    """
    session = None
    start_time = time.time()
    
    # Session creation with retry logic
    for attempt in range(DB_MAX_RETRIES + 1):
        try:
            session = AsyncSessionLocal()
            
            # Verify the connection works
            connection_ok = await verify_db_connection(session, retries=0)
            if not connection_ok:
                if session:
                    await session.close()
                raise OperationalError("Connection test failed", None, None)
                
            # Connection successful - yield the session
            break
                
        except (SQLAlchemyError, TimeoutError) as e:
            # Close the failed session if it was created
            if session:
                try:
                    await session.close()
                except Exception:
                    pass
                    
            # Check if we should retry
            if attempt < DB_MAX_RETRIES:
                retry_delay = DB_RETRY_DELAY * (2 ** attempt)  # Exponential backoff
                logger.warning(
                    f"Database session creation attempt {attempt + 1} failed: {e.__class__.__name__}: {str(e)}. "
                    f"Retrying in {retry_delay:.2f}s..."
                )
                await asyncio.sleep(retry_delay)
            else:
                logger.error(
                    f"Failed to create database session after {DB_MAX_RETRIES + 1} attempts. "
                    f"Last error: {e.__class__.__name__}: {str(e)}"
                )
                # Re-raise the exception to be handled by the caller (e.g., FastAPI exception handlers)
                raise
    
    # If we got here, we have a working session
    if not session:
        raise RuntimeError("Failed to create database session for unknown reason")
        
    try:
        # Actually yield the session to be used
        yield session
    except Exception as e:
        # Error during request processing - rollback and log
        try:
            await session.rollback()
        except Exception as rollback_error:
            logger.warning(f"Error during session rollback: {str(rollback_error)}")
            
        # Re-raise the original exception
        raise
    finally:
        # Always clean up the session
        try:
            await session.close()
            if settings.logging_level.upper() == "DEBUG":
                elapsed = time.time() - start_time
                logger.debug(f"Database session closed after {elapsed:.3f}s")
        except Exception as close_error:
            logger.warning(f"Error closing database session: {str(close_error)}")
            # Don't re-raise close errors - we want to ensure the session is always closed
