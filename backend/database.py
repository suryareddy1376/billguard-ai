from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from dotenv import load_dotenv
from supabase import create_client, Client
import os

load_dotenv()

# Priority to standard DATABASE_URL if SUPABASE_DB_URL is missing
DB_URL = os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL")

if not DB_URL or not DB_URL.startswith("postgresql"):
    raise ValueError("A valid PostgreSQL connection string (SUPABASE_DB_URL or DATABASE_URL) is required.")

# Ensure we use asyncpg driver even if user pasted the raw Supabase URL
if DB_URL.startswith("postgresql://"):
    DB_URL = DB_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Setup Supabase client for storage (optional)
SUPABASE_URL = os.getenv("SUPABASE_PROJECT_URL")
SUPABASE_KEY = os.getenv("SUPABASE_API_KEY")
supabase_client: Client | None = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

import ssl

# Define SSL context to accept the connection when SSL is enforced
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

# Postgres Connection pooling via asyncpg
engine = create_async_engine(
    DB_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    connect_args={
        "prepared_statement_cache_size": 0,
        "statement_cache_size": 0,
        "ssl": ssl_ctx
    }
)

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    from models import BillJob, LineItem, FraudAnalysis, AuditLog  # noqa
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
