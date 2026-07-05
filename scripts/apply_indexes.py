import asyncio
import asyncpg
import os

async def main():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set")
        return
    conn = await asyncpg.connect(db_url)
    with open("scripts/add_indexes.sql") as f:
        sql = f.read()
    await conn.execute(sql)
    await conn.close()
    print("Indexes applied successfully")

if __name__ == "__main__":
    asyncio.run(main())
