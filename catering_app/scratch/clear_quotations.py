import asyncio
from sqlalchemy import text
from catering_app.database import engine

async def clear_data():
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE quotation_items, quotation_sections, quotations CASCADE;"))
        print("Cleared quotation data for revamp.")

if __name__ == "__main__":
    asyncio.run(clear_data())
