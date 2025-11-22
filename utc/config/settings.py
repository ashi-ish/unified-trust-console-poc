"""
Configuration Settings
======================

Centralized configuration using Pydantic V2 Settings.
"""

from pydantic import Field, field_validator, ValidationInfo
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_env: str = Field(default="development")
    app_debug: bool = Field(default=True)
    hmac_secret: str = Field(default="change-me", min_length=32)
    database_url: str = Field(default="sqlite:///./data/utc.db")
    human_approval_rate_per_hour: float = Field(default=0.4, ge=0.0)
    queue_alpha: float = Field(default=0.3, gt=0.0, lt=1.0)
    queue_threshold_low: float = Field(default=0.6, gt=0.0, lt=1.0)
    queue_threshold_high: float = Field(default=0.9, gt=0.0, lt=1.0)

    @field_validator("queue_threshold_high")
    @classmethod
    def validate_thresholds(cls, v: float, info: ValidationInfo) -> float:
        """Ensure high threshold is greater than low threshold."""
        low_threshold = info.data.get("queue_threshold_low")
        if low_threshold is not None and v <= low_threshold:
            raise ValueError(f"queue_threshold_high ({v}) must be > queue_threshold_low ({low_threshold})")
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


settings = Settings()


def get_settings() -> Settings:
    """Get the global settings instance."""
    return settings
