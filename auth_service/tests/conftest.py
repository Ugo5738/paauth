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


@pytest_asyncio.fixture(scope="session")
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
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
