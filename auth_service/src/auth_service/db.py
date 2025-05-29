from typing import AsyncGenerator

import sqlalchemy.util.concurrency as _concurrency

_concurrency._not_implemented = lambda *args, **kwargs: None

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func

from auth_service.config import settings

# Asynchronous database engine
engine: AsyncEngine = create_async_engine(
    settings.auth_service_database_url, echo=settings.logging_level.upper() == "DEBUG"
)

# Session factory for async sessions
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,  # Often useful with async sessions
    autocommit=False,  # Ensure we control transactions explicitly
)

# Base class for ORM models
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Async session generator for dependency injection.
    Handles session creation, yielding, and cleanup (rollback on error, close).
    Commits should typically be handled within the business logic using the session.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()  # Ensure rollback on error within the managed block
            raise
        finally:
            await session.close()
