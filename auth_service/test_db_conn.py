import asyncio
import os
import socket  # Added import

import asyncpg
from dotenv import load_dotenv


async def main():
    load_dotenv()
    db_url_original = os.getenv("AUTH_SERVICE_DATABASE_URL")
    # db_url_original = "postgresql+asyncpg://postgres.ndindbknmovckjouvcvh:Cutesome57381@aws-0-us-east-1.pooler.supabase.com:5432/postgres"

    if not db_url_original:
        print("Error: AUTH_SERVICE_DATABASE_URL not found in environment or .env file.")
        return

    # Modify URL for direct asyncpg connection
    if db_url_original.startswith("postgresql+asyncpg://"):
        db_url_for_asyncpg = db_url_original.replace(
            "postgresql+asyncpg://", "postgresql://", 1
        )
    else:
        db_url_for_asyncpg = db_url_original  # Or handle error if scheme is unexpected

    print(f"Original SQLAlchemy URL: {db_url_original}")
    print(f"Attempting to connect with asyncpg using URL: {db_url_for_asyncpg}")

    try:
        conn = await asyncpg.connect(db_url_for_asyncpg)  # Use modified URL
        print("Successfully connected to the database!")
        version = await conn.fetchval("SELECT version();")
        print(f"PostgreSQL Version: {version}")
        await conn.close()
        print("Connection closed.")
    except asyncpg.exceptions.InvalidPasswordError:
        print("Connection failed: Invalid password.")
    except ConnectionRefusedError:
        print(
            "Connection failed: Connection refused by the server. (Check port and if DB server is listening)"
        )
    except socket.gaierror as e:
        print(
            f"Connection failed: DNS resolution error (socket.gaierror). Could not resolve hostname. Details: {e}"
        )
    except (
        asyncpg.exceptions._base.ClientConfigurationError
    ) as e:  # Catch the DSN error
        print(f"Connection failed: Invalid DSN for asyncpg. Details: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        print(f"Error type: {type(e)}")


if __name__ == "__main__":
    asyncio.run(main())
