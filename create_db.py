import asyncio
import asyncpg
from catering_app.config import settings

async def create_db():
    # Connect to the default postgres database to create a new one
    uri = settings.database_url.replace("postgresql+asyncpg", "postgresql")
    
    # Parse URI or use asyncpg.connect
    # A simple way is connecting to 'postgres' db
    base_uri = uri.rsplit('/', 1)[0] + "/postgres"
    db_name = uri.rsplit('/', 1)[1]
    
    try:
        conn = await asyncpg.connect(base_uri)
        print(f"Connected to {base_uri}")
        # asyncpg doesn't allow CREATE DATABASE in a transaction block
        await conn.execute(f'CREATE DATABASE {db_name}')
        print(f"Database {db_name} created successfully!")
        await conn.close()
    except asyncpg.exceptions.DuplicateDatabaseError:
        print(f"Database {db_name} already exists.")
    except Exception as e:
        print(f"Failed to create database: {e}")

if __name__ == "__main__":
    asyncio.run(create_db())
