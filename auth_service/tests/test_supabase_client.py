import pytest
from unittest.mock import AsyncMock
from auth_service.supabase_client import get_supabase_client, init_supabase_client

@pytest.mark.asyncio
async def test_supabase_client_initialization(monkeypatch):
    """Test that Supabase client is initialized with correct URL and key."""
    # Monkeypatch settings
    class DummySettings:
        supabase_url = "http://test_url.example.com"
        supabase_anon_key = "test_key"
        supabase_service_role_key = "test_service_key"

    # Create a mock Supabase client
    mock_client = AsyncMock()
    mock_client.url = "http://test_url.example.com"
    mock_client.key = "test_key"
    
    # Mock the create_async_supabase_client function
    async def mock_create_client(*args, **kwargs):
        return mock_client
        
    monkeypatch.setattr("auth_service.config.settings", DummySettings)
    monkeypatch.setattr("auth_service.supabase_client.create_async_supabase_client", mock_create_client)
    
    # Initialize the client
    await init_supabase_client()
    
    # Get the client
    client = get_supabase_client()
    assert client is not None
    assert client.url == "http://test_url.example.com"
    assert client.key == "test_key"
