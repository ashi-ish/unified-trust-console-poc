"""
Configuration package.

Exports the singleton settings instance for easy importing.

Usage:
    from utc.config import settings
    
    print(settings.database_url)  # ✅ Works!
"""

from utc.config.settings import settings, get_settings, print_settings

# Make these available when importing from utc.config
__all__ = [
    "settings",
    "get_settings", 
    "print_settings",
]