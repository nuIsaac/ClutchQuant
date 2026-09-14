import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.settings import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True,
                       pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
                       max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")))

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)
