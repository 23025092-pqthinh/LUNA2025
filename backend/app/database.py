import os
import warnings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    host = os.getenv("DB_HOST", os.getenv("POSTGRES_HOST", "localhost"))
    port = os.getenv("POSTGRES_PORT", "5432")
    dbname = os.getenv("POSTGRES_DB", "luna")
    DATABASE_URL = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"


def _create_engine_with_fallback(url: str):
    """Try to create an engine and open a test connection. If that fails,
    fall back to a local SQLite DB so the app can start for development.
    """
    try:
        eng = create_engine(url, future=True)
        # quick test to force auth/connection errors now
        with eng.connect() as conn:
            pass
        return eng
    except Exception as exc:
        warnings.warn(f"Could not connect to database at {url!s}: {exc!s}. Falling back to SQLite ./dev.db")
        sqlite_url = "sqlite:///./dev.db"
        eng = create_engine(sqlite_url, connect_args={"check_same_thread": False}, future=True)
        return eng


engine = _create_engine_with_fallback(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
