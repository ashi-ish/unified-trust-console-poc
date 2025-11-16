"""
Configuration management using Pydantic Settings V2.

This module provides type-safe, validated configuration from environment variables.
Following the 12-Factor App methodology: https://12factor.net/config
"""

from typing import Literal
from pydantic import Field, field_validator, ValidationInfo
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Pydantic V2 automatically:
    - Converts types (string "8000" → int 8000)
    - Validates values (raises error if invalid)
    - Loads from .env file
    """
    
    # ========================================
    # Application Settings
    # ========================================
    
    app_env: Literal["development", "production", "testing"] = Field(
        default="development",
        description="Application environment"
    )
    
    app_debug: bool = Field(
        default=True,
        description="Enable debug mode (detailed error messages)"
    )
    
    app_host: str = Field(
        default="0.0.0.0",
        description="Host to bind the application"
    )
    
    app_port: int = Field(
        default=8000,
        description="Port to bind the application",
        ge=1,
        le=65535
    )
    
    # ========================================
    # Security Settings
    # ========================================
    
    hmac_secret: str = Field(
        default="change-me-in-production-use-openssl-rand-hex-32",
        description="Secret key for HMAC signing (JWT receipts)",
        min_length=32
    )
    
    jwt_algorithm: str = Field(
        default="HS256",
        description="JWT signing algorithm"
    )
    
    # ========================================
    # Database Settings
    # ========================================
    
    database_url: str = Field(
        default="sqlite:///./data/utc.db",
        description="Database connection URL"
    )
    
    # ========================================
    # Queueing Configuration
    # ========================================
    
    human_approval_rate_per_hour: float = Field(
        default=0.4,
        description="Maximum human approvals per hour (service rate)",
        gt=0.0,
        le=10.0
    )
    
    queue_alpha: float = Field(
        default=0.3,
        description="EWMA smoothing factor for arrival rate calculation",
        gt=0.0,
        lt=1.0
    )
    
    queue_threshold_low: float = Field(
        default=0.6,
        description="Low utilization threshold (below this = permissive)",
        ge=0.0,
        le=1.0
    )
    
    queue_threshold_high: float = Field(
        default=0.9,
        description="High utilization threshold (above this = read-only)",
        ge=0.0,
        le=1.0
    )
    
    auto_relax_window_min: int = Field(
        default=60,
        description="Minutes to wait before auto-relaxing protection level",
        ge=1
    )
    
    # ========================================
    # Trust Data Exchange Settings
    # ========================================
    
    tdx_enabled: bool = Field(
        default=True,
        description="Enable Trust Data Exchange background job"
    )
    
    tdx_interval_hours: int = Field(
        default=1,
        description="Hours between TDX ingestion runs",
        ge=1,
        le=24
    )
    
    # ========================================
    # Logging Settings
    # ========================================
    
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level"
    )
    
    # ========================================
    # Validators (Custom Validation Logic)
    # ========================================
    
    @field_validator("queue_threshold_high")
    @classmethod
    def validate_thresholds(cls, v: float, info: ValidationInfo) -> float:
        """
        Ensure high threshold is greater than low threshold.
        
        Args:
            v: The value being validated (queue_threshold_high)
            info: ValidationInfo object containing other field data
        
        Returns:
            The validated value
        
        Raises:
            ValueError: If high <= low
        """
        # Access previously validated fields via info.data
        low_threshold = info.data.get("queue_threshold_low")
        
        if low_threshold is not None and v <= low_threshold:
            raise ValueError(
                f"queue_threshold_high ({v}) must be greater than "
                f"queue_threshold_low ({low_threshold})"
            )
        return v
    
    @field_validator("hmac_secret")
    @classmethod
    def validate_secret_in_production(cls, v: str, info: ValidationInfo) -> str:
        """
        Warn if using default secret in production.
        
        Args:
            v: The value being validated (hmac_secret)
            info: ValidationInfo object containing other field data
        
        Returns:
            The validated value
        
        Raises:
            ValueError: If default secret is used in production
        """
        # Access previously validated fields via info.data
        app_env = info.data.get("app_env")
        
        if app_env == "production" and "change-me" in v.lower():
            raise ValueError(
                "⚠️  SECURITY WARNING: You're using the default HMAC_SECRET in production! "
                "Generate a secure secret with: openssl rand -hex 32"
            )
        return v
    
    # ========================================
    # Pydantic Configuration
    # ========================================
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# ========================================
# Singleton Instance
# ========================================

settings = Settings()


# ========================================
# Helper Functions
# ========================================

def get_settings() -> Settings:
    """
    Dependency injection helper for FastAPI.
    
    Usage:
        from fastapi import Depends
        from utc.config import get_settings
        
        @app.get("/status")
        def status(settings: Settings = Depends(get_settings)):
            return {"env": settings.app_env}
    """
    return settings


def print_settings() -> None:
    """
    Pretty-print all settings (useful for debugging).
    Masks sensitive values like secrets.
    """
    print("=" * 60)
    print("⚙️  Application Configuration")
    print("=" * 60)
    
    for field_name, field_info in Settings.model_fields.items():
        value = getattr(settings, field_name)
        
        # Mask sensitive values
        if "secret" in field_name.lower() or "password" in field_name.lower():
            if isinstance(value, str) and len(value) > 8:
                masked_value = value[:4] + "*" * (len(value) - 8) + value[-4:]
            else:
                masked_value = "****"
            print(f"  {field_name:30s} = {masked_value}")
        else:
            print(f"  {field_name:30s} = {value}")
    
    print("=" * 60)


# ========================================
# Startup Validation
# ========================================

if __name__ == "__main__":
    """
    Test the settings by running this file directly:
        python -m utc.config.settings
    """
    try:
        print_settings()
        print("\n✅ Configuration loaded successfully!")
        print("✅ Using Pydantic V2 field validators")
    except Exception as e:
        print(f"\n❌ Configuration error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)