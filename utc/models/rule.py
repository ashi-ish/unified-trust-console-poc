"""
Rule model for policy configuration.

A Rule represents a single policy control (e.g., "writes_require_approval").
There are only 2 rules in the system, defined in core/constants.py.

Why a database table for only 2 rules?
- Dynamic configuration (toggle via API, no code changes)
- Audit trail (track when rules changed)
- Persistence (survives app restart)
- Future-proof (easy to add more rules later)
"""

from typing import Optional
from sqlalchemy import String, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column

from utc.models.base import Base, BaseModel


class Rule(BaseModel, Base):
    """
    Policy rule configuration.
    
    Attributes:
        id: Auto-incrementing primary key
        key: Unique rule identifier (e.g., "writes_require_approval")
        value: Rule state (0=OFF, 1=ON)
        created_at: When rule was first created (from BaseModel)
        updated_at: When rule was last modified (from BaseModel)
    
    Example:
        # Create a rule
        rule = Rule(key="writes_require_approval", value=1)
        db.add(rule)
        db.commit()
        
        # Query a rule
        rule = db.query(Rule).filter_by(key="writes_require_approval").first()
        if rule.value == 1:
            print("Writes require approval!")
    """
    
    __tablename__ = "rules"
    
    # ========================================
    # Primary Key
    # ========================================
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Auto-incrementing primary key"
    )
    
    # ========================================
    # Rule Configuration
    # ========================================
    
    key: Mapped[str] = mapped_column(
        String(100),
        unique=True,  # Each rule key can only exist once
        nullable=False,
        index=True,  # Fast lookups by key
        comment="Unique rule identifier (e.g., 'writes_require_approval')"
    )
    
    value: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,  # Default to OFF
        comment="Rule state: 0=OFF, 1=ON"
    )
    
    # ========================================
    # Indexes
    # ========================================
    
    # Composite index for fast filtering
    # (SQLAlchemy 2.0 syntax for table-level indexes)
    __table_args__ = (
        Index('ix_rules_key_value', 'key', 'value'),
        {'comment': 'Policy rules configuration table'}
    )
    
    # ========================================
    # Business Logic Methods
    # ========================================
    
    def is_enabled(self) -> bool:
        """
        Check if rule is enabled.
        
        Returns:
            True if rule is ON (value=1), False otherwise
        
        Example:
            rule = Rule(key="writes_require_approval", value=1)
            if rule.is_enabled():
                print("Approval required!")
        
        Why a method instead of checking value directly?
        - Encapsulation: Business logic stays in the model
        - Readability: rule.is_enabled() is clearer than rule.value == 1
        - Future-proof: Logic can change without affecting callers
        """
        return self.value == 1
    
    def enable(self) -> None:
        """
        Enable this rule (set value to 1).
        
        Example:
            rule = db.query(Rule).filter_by(key="read_only_for_risky").first()
            rule.enable()
            db.commit()
        
        Note: Remember to commit the transaction!
        """
        self.value = 1
    
    def disable(self) -> None:
        """
        Disable this rule (set value to 0).
        
        Example:
            rule = db.query(Rule).filter_by(key="writes_require_approval").first()
            rule.disable()
            db.commit()
        """
        self.value = 0
    
    def toggle(self) -> None:
        """
        Toggle rule state (ON → OFF or OFF → ON).
        
        Example:
            rule = db.query(Rule).filter_by(key="writes_require_approval").first()
            rule.toggle()  # If ON, becomes OFF; if OFF, becomes ON
            db.commit()
        """
        self.value = 1 if self.value == 0 else 0
    
    # ========================================
    # Validation
    # ========================================
    
    def __init__(self, **kwargs):
        """
        Initialize a Rule with validation.
        
        Validates:
        - key is not empty
        - value is 0 or 1
        
        Raises:
            ValueError: If validation fails
        """
        super().__init__(**kwargs)
        
        # Validate key
        if not self.key or not self.key.strip():
            raise ValueError("Rule key cannot be empty")
        
        # Validate value
        if self.value not in (0, 1):
            raise ValueError(f"Rule value must be 0 or 1, got {self.value}")
    
    # ========================================
    # String Representation
    # ========================================
    
    def __repr__(self) -> str:
        """
        String representation for debugging.
        
        Example output:
            <Rule(id=1, key='writes_require_approval', value=1, enabled=True)>
        """
        status = "enabled" if self.is_enabled() else "disabled"
        return (
            f"<Rule(id={self.id}, key='{self.key}', "
            f"value={self.value}, {status})>"
        )
    
    def __str__(self) -> str:
        """
        Human-readable string representation.
        
        Example output:
            "writes_require_approval: ON"
        """
        status = "ON" if self.is_enabled() else "OFF"
        return f"{self.key}: {status}"


# ========================================
# Helper Functions
# ========================================

def get_rule_by_key(db, key: str) -> Optional[Rule]:
    """
    Get a rule by its key.
    
    Args:
        db: Database session
        key: Rule key to look up
    
    Returns:
        Rule instance or None if not found
    
    Example:
        from utc.database import get_db_context
        
        with get_db_context() as db:
            rule = get_rule_by_key(db, "writes_require_approval")
            if rule and rule.is_enabled():
                print("Approval required!")
    
    Why a helper function?
    - DRY: Common query pattern used everywhere
    - Consistency: Same lookup logic across codebase
    - Testability: Easy to mock
    """
    return db.query(Rule).filter_by(key=key).first()


def is_rule_enabled(db, key: str) -> bool:
    """
    Check if a rule is enabled.
    
    Args:
        db: Database session
        key: Rule key to check
    
    Returns:
        True if rule exists and is enabled, False otherwise
    
    Example:
        with get_db_context() as db:
            if is_rule_enabled(db, "writes_require_approval"):
                return "Approval required"
    
    Safe: Returns False if rule doesn't exist (fail-safe default)
    """
    rule = get_rule_by_key(db, key)
    return rule.is_enabled() if rule else False


def toggle_rule(db, key: str) -> bool:
    """
    Toggle a rule's state.
    
    Args:
        db: Database session
        key: Rule key to toggle
    
    Returns:
        New state (True=enabled, False=disabled)
    
    Raises:
        ValueError: If rule doesn't exist
    
    Example:
        with get_db_context() as db:
            new_state = toggle_rule(db, "writes_require_approval")
            print(f"Rule is now: {'ON' if new_state else 'OFF'}")
    """
    rule = get_rule_by_key(db, key)
    if not rule:
        raise ValueError(f"Rule not found: {key}")
    
    rule.toggle()
    db.commit()
    return rule.is_enabled()