from supabase import AsyncClient, create_client
import auth_service.config as config


def get_supabase_client() -> AsyncClient:
    """
    Initialize and return Supabase AsyncClient or dummy client in tests.
    """
    url = config.settings.supabase_url
    key = config.settings.supabase_anon_key

    class DummyClient:
        def __init__(self, url, key):
            self.url = url
            self.key = key

    if not url.startswith("http://") and not url.startswith("https://"):
        return DummyClient(url, key)

    client = create_client(url, key)
    # expose settings for testing
    client.url = url
    client.key = key
    return client
