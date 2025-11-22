"""
Base Model
==========

Provides common functionality for all database models.
"""

from datetime import datetime
from typing import Any, Dict
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


class TimestampMixin:
    """Mixin that adds created_at and updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )


class SerializationMixin:
    """Mixin that adds to_dict() serialization method."""

    def to_dict(self, exclude: set = None) -> Dict[str, Any]:
        """Convert model instance to dictionary."""
        exclude = exclude or set()
        result = {}
        for column in self.__table__.columns:
            if column.name in exclude:
                continue
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                result[column.name] = value.isoformat()
            else:
                result[column.name] = value
        return result


class BaseModel(TimestampMixin, SerializationMixin):
    """Base model combining timestamp and serialization mixins."""
    pass
