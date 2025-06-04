#!/usr/bin/env python3
import asyncio
from sqlalchemy import create_engine, text

async def check_schemas():
    engine = create_engine('postgresql://postgres:postgres@db:5432/postgres')
    with engine.connect() as conn:
        print("Schemas:")
        result = conn.execute(text('SELECT schema_name FROM information_schema.schemata'))
        for row in result:
            print(row[0])
        
        print("\nTables:")
        result = conn.execute(text("SELECT table_schema, table_name FROM information_schema.tables WHERE table_type = 'BASE TABLE'"))
        for row in result:
            print(f"{row[0]}.{row[1]}")

if __name__ == "__main__":
    asyncio.run(check_schemas())
