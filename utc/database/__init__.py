"""
Database configuration and session management.

Note: We defer imports to avoid circular import issues
when running modules directly (e.g., python -m utc.database.session)
"""

# Import only what's needed, when needed
# This prevents circular import warnings

def __getattr__(name):
    """
    Lazy import pattern to avoid circular imports.
    
    When you do: from utc.database import engine
    This function runs and imports it dynamically.
    
    Why?
    - Avoids importing session.py when the package loads
    - Only imports when actually needed
    - Prevents circular import warnings
    """
    if name in ["engine", "SessionLocal", "get_db", "get_db_context", 
                "check_db_connection", "get_db_info"]:
        from utc.database.session import (
            engine,
            SessionLocal, 
            get_db,
            get_db_context,
            check_db_connection,
            get_db_info,
        )
        return locals()[name]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    "engine",
    "SessionLocal",
    "get_db",
    "get_db_context",
    "check_db_connection",
    "get_db_info",
]