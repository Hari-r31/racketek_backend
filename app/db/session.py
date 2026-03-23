"""
DB session — SQLAlchemy engine + session factory

M1 FIX: pool_size and max_overflow reduced to PgBouncer-compatible values.
         With 4 Uvicorn workers and pool_size=5, max_overflow=10:
           - Max connections per worker  = 15
           - Max connections for 4 workers = 60
           - PgBouncer server pool can absorb this comfortably
         pool_timeout added — requests queue max 30 s before raising OperationalError.
         pool_recycle added — connections recycled after 1 h to avoid stale connections.

Production recommendation: run PgBouncer in transaction-pooling mode in front of
Postgres. Point DATABASE_URL at PgBouncer (port 6432 typically). Set
pool_size=2, max_overflow=3 per worker when using PgBouncer (it does the pooling).
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,      # test connections before use — detects stale sockets
    pool_size=5,             # M1 FIX: reduced from 10 (was too high for multi-worker)
    max_overflow=10,         # M1 FIX: reduced from 20
    pool_timeout=30,         # seconds to wait for a connection from the pool
    pool_recycle=3600,       # recycle connections older than 1 h
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
