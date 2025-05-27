from typing import AsyncGenerator

import sqlalchemy.util.concurrency as _concurrency
_concurrency._not_implemented = lambda *args, **kwargs: None

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from auth_service.config import settings

# Asynchronous database engine
engine: AsyncEngine = create_async_engine(
    settings.auth_service_database_url,
    echo=True,
    future=True
)

# Session factory for async sessions
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Base class for ORM models
Base = declarative_base()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Async session generator for dependency injection.
    """
    async with AsyncSessionLocal() as session:
        yield session
