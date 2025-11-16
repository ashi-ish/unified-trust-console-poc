"""
Database session management and connection handling.

This module provides:
- Database engine creation
- Session factory (connection pool)
- Context managers for safe database operations
- Connection lifecycle management

Why separate this?
- DRY: Single place to configure database
- Testability: Easy to swap real DB with test DB
- Connection pooling: Reuse connections efficiently
- Transaction management: Automatic commit/rollback
"""

from typing import Generator
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from utc.config import settings


# ========================================
# Engine Creation
# ========================================

def create_db_engine():
    """
    Create SQLAlchemy engine with appropriate settings.
    
    Engine = The source of database connections.
    Think of it as a connection factory.
    
    Why different settings for SQLite vs PostgreSQL?
    - SQLite: File-based, needs special configuration
    - PostgreSQL: Server-based, different optimizations
    
    Returns:
        Engine: SQLAlchemy engine instance
    """
    connect_args = {}
    
    # SQLite-specific configuration
    if settings.database_url.startswith("sqlite"):
        connect_args = {
            # SQLite doesn't support multiple connections by default
            # check_same_thread: Allow usage across threads (needed for FastAPI)
            "check_same_thread": False,
        }
        
        # For in-memory SQLite, use StaticPool
        # (keeps database alive between connections)
        if ":memory:" in settings.database_url:
            return create_engine(
                settings.database_url,
                connect_args=connect_args,
                poolclass=StaticPool,
                echo=settings.app_debug,  # Log SQL queries in debug mode
            )
    
    # Standard engine for file-based SQLite or PostgreSQL
    return create_engine(
        settings.database_url,
        connect_args=connect_args,
        echo=settings.app_debug,  # Log all SQL queries when debugging
        pool_pre_ping=True,  # Verify connections before using (prevents stale connections)
        pool_recycle=3600,  # Recycle connections after 1 hour
    )


# Create the global engine instance
engine = create_db_engine()


# ========================================
# Session Factory
# ========================================

# SessionLocal is a factory that creates new Session instances
# Each session represents a "workspace" for database operations
SessionLocal = sessionmaker(
    autocommit=False,  # Don't auto-commit (we control transactions)
    autoflush=False,   # Don't auto-flush (explicit is better than implicit)
    bind=engine,       # Bind to our engine
)


# ========================================
# Database Session Dependency (for FastAPI)
# ========================================

def get_db() -> Generator[Session, None, None]:
    """
    Dependency injection for FastAPI routes.
    
    Yields a database session and ensures it's closed after use.
    Even if an exception occurs, the session is properly closed.
    
    Usage in FastAPI:
        @app.get("/rules")
        def get_rules(db: Session = Depends(get_db)):
            rules = db.query(Rule).all()
            return rules
    
    Why Generator?
    - Automatically calls cleanup code (closes session)
    - FastAPI knows how to handle generators as dependencies
    - Prevents connection leaks
    
    Yields:
        Session: Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()  # Always close, even if exception occurs


# ========================================
# Context Manager (for Scripts & Background Jobs)
# ========================================

@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager for database sessions in scripts.
    
    Usage:
        with get_db_context() as db:
            rule = db.query(Rule).first()
            print(rule.key)
        # Session automatically closed here
    
    Why context manager?
    - Automatic cleanup (Pythonic!)
    - Ensures commit/rollback
    - Prevents connection leaks
    
    Yields:
        Session: Database session
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()  # Commit on success
    except Exception:
        db.rollback()  # Rollback on error
        raise  # Re-raise the exception
    finally:
        db.close()  # Always close


# ========================================
# SQLite-specific Optimizations
# ========================================

if settings.database_url.startswith("sqlite"):
    # Enable foreign key constraints (SQLite has them disabled by default!)
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        """
        Configure SQLite connection when it's created.
        
        Why?
        - Foreign keys OFF by default in SQLite (shocking!)
        - WAL mode: Better concurrency
        - Synchronous NORMAL: Faster writes, still safe
        
        This runs automatically for each new connection.
        """
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")  # Enable foreign key constraints
        cursor.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging (better concurrency)
        cursor.execute("PRAGMA synchronous=NORMAL")  # Balance safety/speed
        cursor.close()


# ========================================
# Helper Functions
# ========================================

def check_db_connection() -> bool:
    """
    Verify database connection is working.
    
    Usage:
        if check_db_connection():
            print("✅ Database connected!")
        else:
            print("❌ Database connection failed!")
    
    Returns:
        bool: True if connection successful, False otherwise
    """
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")  # Simple query to test connection
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


def get_db_info() -> dict:
    """
    Get database information (useful for debugging).
    
    Returns:
        dict: Database metadata
    """
    return {
        "url": str(engine.url),
        "driver": engine.driver,
        "pool_size": engine.pool.size() if hasattr(engine.pool, "size") else "N/A",
        "checked_out_connections": engine.pool.checkedout() if hasattr(engine.pool, "checkedout") else "N/A",
    }


# ========================================
# Startup Test
# ========================================

if __name__ == "__main__":
    """
    Test database connection by running this file:
        python -m utc.database.session
    """
    print("=" * 60)
    print("🗄️  Database Connection Test")
    print("=" * 60)
    
    print(f"\n📍 Database URL: {settings.database_url}")
    
    if check_db_connection():
        print("✅ Database connection successful!")
        
        info = get_db_info()
        print("\n📊 Database Info:")
        for key, value in info.items():
            print(f"  {key:25s} = {value}")
    else:
        print("❌ Database connection failed!")
        exit(1)
    
    print("\n" + "=" * 60)