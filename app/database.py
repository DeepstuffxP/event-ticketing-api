import asyncpg
from contextlib import asynccontextmanager
import os 
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost/ticketing")

class Database:
    pool: asyncpg.Pool = None 

db = Database()

async def connect_db():
    db.pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)

async def disconnect_db():
    await db.pool.close()

def get_pool() -> asyncpg.Pool:
    return db.pool