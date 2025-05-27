import pytest
from auth_service.supabase_client import get_supabase_client

@pytest.mark.asyncio
async def test_supabase_client_initialization(monkeypatch):
    """Test that Supabase client is initialized with correct URL and key."""
    # Monkeypatch settings
    class DummySettings:
        supabase_url = "test_url"
        supabase_anon_key = "test_key"

    monkeypatch.setattr("auth_service.config.settings", DummySettings)
    client = get_supabase_client()
    assert client.url == "test_url"
    assert client.key == "test_key"
