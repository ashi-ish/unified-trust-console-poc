"""
Database Session Management
============================

Handles database connections and session lifecycle.
"""

import os
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from utc.config import settings


def create_db_engine():
    """Create and configure the database engine."""
    database_url = settings.database_url

    # SQLite-specific configuration
    if database_url.startswith("sqlite"):
        # Ensure data directory exists
        if ":///" in database_url:
            db_path = database_url.split(":///")[1]
            if not db_path.startswith(":memory:"):
                db_dir = os.path.dirname(db_path)
                if db_dir and not os.path.exists(db_dir):
                    os.makedirs(db_dir, exist_ok=True)

        # Create engine with SQLite optimizations
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=settings.app_debug
        )

        # Enable foreign keys and WAL mode for SQLite
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    else:
        engine = create_engine(database_url, echo=settings.app_debug)

    return engine


# Create global engine and session factory
engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.

    Usage:
        with get_db_context() as db:
            # do stuff with db
            db.commit()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency injection for FastAPI routes.

    Usage:
        @app.get("/")
        def index(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all_tables(engine_instance=None):
    """Create all tables in the database."""
    from utc.models.base import Base

    if engine_instance is None:
        engine_instance = engine

    Base.metadata.create_all(bind=engine_instance)


def drop_all_tables(engine_instance=None):
    """Drop all tables in the database."""
    from utc.models.base import Base

    if engine_instance is None:
        engine_instance = engine

    Base.metadata.drop_all(bind=engine_instance)
