"""
Base model class for all database models.

Provides common functionality:
- Declarative Base (SQLAlchemy ORM foundation)
- Timestamps (created_at, updated_at)
- Serialization (to_dict, from_dict)
- String representation (__repr__)

Why a base model?
- DRY: Common fields and methods in one place
- Consistency: All models behave the same way
- Maintainability: Update once, affects all models
- Testability: Easier to mock and test
"""

from datetime import datetime
from typing import Any, Dict
from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


# ========================================
# Declarative Base
# ========================================

class Base(DeclarativeBase):
    """
    SQLAlchemy Declarative Base.
    
    All models inherit from this to become database tables.
    
    SQLAlchemy 2.0 uses DeclarativeBase instead of declarative_base().
    This new approach provides better type hints and IDE support.
    """
    pass


# ========================================
# Base Model Mixin
# ========================================

class TimestampMixin:
    """
    Mixin class for automatic timestamp management.
    
    Provides:
    - created_at: Set once when record is created
    - updated_at: Updated every time record is modified
    
    Why a mixin?
    - Not all models may need timestamps
    - Composition over inheritance (flexible)
    - Can mix-and-match with other mixins
    """
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),  # Database sets this automatically
        nullable=False,
        comment="Timestamp when record was created"
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),  # Initial value
        onupdate=func.now(),  # Update on every modification
        nullable=False,
        comment="Timestamp when record was last updated"
    )


class SerializationMixin:
    """
    Mixin class for JSON serialization.
    
    Provides:
    - to_dict(): Convert model instance to dictionary
    - from_dict(): Create model instance from dictionary
    - __repr__(): Readable string representation
    
    Why separate mixin?
    - Single Responsibility Principle
    - Some models might need custom serialization
    - Easy to override in specific models
    """
    
    def to_dict(self, exclude: set = None) -> Dict[str, Any]:
        """
        Convert model instance to dictionary.
        
        Args:
            exclude: Set of field names to exclude from output
        
        Returns:
            Dictionary representation of the model
        
        Example:
            rule = Rule(key="test", value=1)
            data = rule.to_dict()
            # {"id": 1, "key": "test", "value": 1, "created_at": "2024-01-01T00:00:00"}
        
        Why not use Pydantic?
        - This is for database models
        - Pydantic schemas are for API contracts (we'll create those separately)
        - Separation of concerns!
        """
        exclude = exclude or set()
        result = {}
        
        # Iterate through all columns
        for column in self.__table__.columns:
            if column.name in exclude:
                continue
            
            value = getattr(self, column.name)
            
            # Handle datetime serialization
            if isinstance(value, datetime):
                result[column.name] = value.isoformat()
            else:
                result[column.name] = value
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """
        Create model instance from dictionary.
        
        Args:
            data: Dictionary of field values
        
        Returns:
            Model instance
        
        Example:
            data = {"key": "test", "value": 1}
            rule = Rule.from_dict(data)
        
        Why classmethod?
        - Called on the class, not instance
        - Factory pattern (creates instances)
        """
        # Filter to only valid column names
        valid_keys = {c.name for c in cls.__table__.columns}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        
        return cls(**filtered_data)
    
    def __repr__(self) -> str:
        """
        Readable string representation for debugging.
        
        Example:
            rule = Rule(key="test", value=1)
            print(rule)
            # Output: <Rule(id=1, key='test', value=1)>
        
        Why important?
        - Debugging (print statements)
        - Logging
        - Interactive Python shell
        """
        # Get primary key column name
        pk_columns = [c.name for c in self.__table__.primary_key.columns]
        pk_values = [f"{col}={getattr(self, col)!r}" for col in pk_columns]
        
        # Add a few other key fields
        other_fields = []
        for column in list(self.__table__.columns)[:3]:  # First 3 columns
            if column.name not in pk_columns:
                value = getattr(self, column.name, None)
                other_fields.append(f"{column.name}={value!r}")
        
        fields = ", ".join(pk_values + other_fields)
        return f"<{self.__class__.__name__}({fields})>"


# ========================================
# Combined Base Model
# ========================================

class BaseModel(TimestampMixin, SerializationMixin):
    """
    Base model combining all mixins.
    
    Most models should inherit from this.
    
    Usage:
        class Rule(BaseModel, Base):
            __tablename__ = "rules"
            id = mapped_column(Integer, primary_key=True)
            key = mapped_column(String(100))
    
    Provides:
    - Automatic timestamps (created_at, updated_at)
    - Serialization (to_dict, from_dict)
    - String representation (__repr__)
    
    Why multiple inheritance?
    - Composition: Mix and match features
    - Flexibility: Can use mixins individually if needed
    - DRY: Each mixin has single responsibility
    """
    pass


# ========================================
# Helper Functions
# ========================================

def get_all_models():
    """
    Get all models that inherit from Base.
    
    Useful for:
    - Creating all tables
    - Migrations
    - Introspection
    
    Returns:
        List of model classes
    """
    return Base.__subclasses__()


def create_all_tables(engine):
    """
    Create all database tables.
    
    Args:
        engine: SQLAlchemy engine
    
    Example:
        from utc.database import engine
        from utc.models.base import create_all_tables
        
        create_all_tables(engine)
    """
    Base.metadata.create_all(bind=engine)


def drop_all_tables(engine):
    """
    Drop all database tables.
    
    WARNING: This deletes all data!
    Only use in development/testing.
    
    Args:
        engine: SQLAlchemy engine
    """
    Base.metadata.drop_all(bind=engine)