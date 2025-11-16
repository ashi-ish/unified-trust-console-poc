"""
Receipt model for decision audit trail.

A Receipt is an immutable, signed record of a decision made by the Decision Service.
Every action (ALLOW, DENY, REQUIRE_APPROVAL) generates a receipt.

Why receipts?
- Audit trail: Who did what, when, and why
- Non-repudiation: Cryptographic signatures prevent tampering
- Compliance: Evidence for audits (SOC 2, GDPR, etc.)
- Debugging: Trace why a decision was made

Receipts are NEVER updated after creation (immutable).
"""

import json
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime

from sqlalchemy import String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from utc.models.base import Base, BaseModel
from utc.core.constants import DecisionType


class Receipt(BaseModel, Base):
    """
    Immutable decision receipt with cryptographic signature.
    
    Attributes:
        id: UUID primary key (globally unique)
        subject: Who made the request (e.g., "agent-42", "user-123")
        action: What was requested (e.g., "write:/payments", "read:/users")
        decision: Outcome (ALLOW, DENY, REQUIRE_APPROVAL, POLICY_CHANGE)
        rules_json: Which rules were evaluated (stored as JSON array)
        reason: Human-readable explanation
        payload_hash: SHA-256 hash of request body (for verification)
        meta_json: Metadata (queueing metrics, context) as JSON
        signature: JWT signature of the receipt (tamper-proof)
        created_at: When decision was made (from BaseModel)
        updated_at: Should never change (receipts are immutable)
    
    Example:
        receipt = Receipt(
            id=str(uuid.uuid4()),
            subject="agent-42",
            action="write:/payments",
            decision=DecisionType.REQUIRE_APPROVAL,
            rules=["writes_require_approval"],
            reason="Approval required for writes",
            payload_hash="sha256:abc123...",
            meta={"lambda_est": 0.2, "mu_est": 1.0, "rho": 0.2}
        )
    """
    
    __tablename__ = "receipts"
    
    # ========================================
    # Primary Key (UUID)
    # ========================================
    
    id: Mapped[str] = mapped_column(
        String(36),  # UUID4 format: "550e8400-e29b-41d4-a716-446655440000"
        primary_key=True,
        comment="UUID primary key (globally unique identifier)"
    )
    
    # ========================================
    # Core Fields
    # ========================================
    
    subject: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,  # Fast lookups by subject
        comment="Who made the request (agent ID, user ID, etc.)"
    )
    
    action: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,  # Fast lookups by action
        comment="What was requested (e.g., 'write:/payments')"
    )
    
    decision: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,  # Fast filtering by decision type
        comment="Decision outcome (ALLOW, DENY, REQUIRE_APPROVAL, POLICY_CHANGE)"
    )
    
    # ========================================
    # Context Fields
    # ========================================
    
    rules_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
        comment="Which rules applied (JSON array of rule keys)"
    )
    
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Human-readable explanation of the decision"
    )
    
    payload_hash: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Hash of the request payload (e.g., 'sha256:abc123...')"
    )
    
    # ========================================
    # Metadata (JSON)
    # ========================================
    
    meta_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="{}",
        comment="Queueing metrics and context (JSON object)"
    )
    
    # ========================================
    # Signature (Tamper-Proof)
    # ========================================
    
    signature: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,  # Signature added after receipt creation
        comment="JWT signature (cryptographically signed receipt)"
    )
    
    # ========================================
    # Indexes
    # ========================================
    
    __table_args__ = (
        Index('ix_receipts_subject_created', 'subject', 'created_at'),
        Index('ix_receipts_decision_created', 'decision', 'created_at'),
        Index('ix_receipts_action_created', 'action', 'created_at'),
        {'comment': 'Immutable decision receipts (audit trail)'}
    )
    
    # ========================================
    # Property Accessors (JSON Deserialization)
    # ========================================
    
    @property
    def rules(self) -> List[str]:
        """
        Get rules as Python list (deserialize from JSON).
        
        Returns:
            List of rule keys that were evaluated
        
        Example:
            receipt = Receipt(rules_json='["writes_require_approval"]')
            print(receipt.rules)  # ["writes_require_approval"]
        
        Why property?
        - Transparent: Access like a normal attribute
        - Lazy: Only deserialize when needed
        - Read-only: Can't accidentally modify
        """
        try:
            return json.loads(self.rules_json)
        except (json.JSONDecodeError, TypeError):
            return []
    
    @rules.setter
    def rules(self, value: List[str]) -> None:
        """
        Set rules from Python list (serialize to JSON).
        
        Args:
            value: List of rule keys
        
        Example:
            receipt.rules = ["writes_require_approval", "read_only_for_risky"]
            # Internally stores: '["writes_require_approval", "read_only_for_risky"]'
        """
        self.rules_json = json.dumps(value)
    
    @property
    def meta(self) -> Dict[str, Any]:
        """
        Get metadata as Python dict (deserialize from JSON).
        
        Returns:
            Dictionary of metadata (queueing metrics, etc.)
        
        Example:
            receipt = Receipt(meta_json='{"lambda_est": 0.2}')
            print(receipt.meta["lambda_est"])  # 0.2
        """
        try:
            return json.loads(self.meta_json)
        except (json.JSONDecodeError, TypeError):
            return {}
    
    @meta.setter
    def meta(self, value: Dict[str, Any]) -> None:
        """
        Set metadata from Python dict (serialize to JSON).
        
        Args:
            value: Dictionary of metadata
        
        Example:
            receipt.meta = {
                "lambda_est": 0.2,
                "mu_est": 1.0,
                "rho": 0.2
            }
        """
        self.meta_json = json.dumps(value)
    
    # ========================================
    # Business Logic Methods
    # ========================================
    
    def is_allowed(self) -> bool:
        """Check if action was allowed."""
        return self.decision == DecisionType.ALLOW.value
    
    def is_denied(self) -> bool:
        """Check if action was denied."""
        return self.decision == DecisionType.DENY.value
    
    def requires_approval(self) -> bool:
        """Check if action requires approval."""
        return self.decision == DecisionType.REQUIRE_APPROVAL.value
    
    def is_policy_change(self) -> bool:
        """Check if this documents a policy change."""
        return self.decision == DecisionType.POLICY_CHANGE.value
    
    def is_signed(self) -> bool:
        """Check if receipt has been signed."""
        return self.signature is not None and len(self.signature) > 0
    
    # ========================================
    # Serialization (Override to_dict)
    # ========================================
    
    def to_dict(self, exclude: set = None) -> Dict[str, Any]:
        """
        Convert to dictionary with deserialized JSON fields.
        
        Override BaseModel.to_dict() to return deserialized
        rules and meta instead of raw JSON strings.
        
        Returns:
            Dictionary with all fields, JSON fields deserialized
        """
        exclude = exclude or set()
        result = super().to_dict(exclude=exclude | {'rules_json', 'meta_json'})
        
        # Add deserialized JSON fields
        if 'rules' not in exclude:
            result['rules'] = self.rules
        if 'meta' not in exclude:
            result['meta'] = self.meta
        
        return result
    
    # ========================================
    # Validation
    # ========================================
    
    def __init__(self, **kwargs):
        """
        Initialize Receipt with validation.
        
        Auto-generates UUID if not provided.
        Validates decision type.
        """
        # Auto-generate UUID if not provided
        if 'id' not in kwargs:
            kwargs['id'] = str(uuid.uuid4())
        
        # Handle rules list → JSON conversion
        if 'rules' in kwargs and 'rules_json' not in kwargs:
            rules_list = kwargs.pop('rules')
            kwargs['rules_json'] = json.dumps(rules_list)
        
        # Handle meta dict → JSON conversion
        if 'meta' in kwargs and 'meta_json' not in kwargs:
            meta_dict = kwargs.pop('meta')
            kwargs['meta_json'] = json.dumps(meta_dict)
        
        super().__init__(**kwargs)
        
        # Validate decision type
        valid_decisions = [d.value for d in DecisionType]
        if self.decision not in valid_decisions:
            raise ValueError(
                f"Invalid decision type: {self.decision}. "
                f"Must be one of: {valid_decisions}"
            )
    
    # ========================================
    # String Representation
    # ========================================
    
    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return (
            f"<Receipt(id='{self.id[:8]}...', "
            f"subject='{self.subject}', "
            f"action='{self.action}', "
            f"decision='{self.decision}')>"
        )
    
    def __str__(self) -> str:
        """Human-readable representation."""
        return (
            f"Receipt {self.id[:8]}: {self.decision} for {self.action} "
            f"by {self.subject} - {self.reason}"
        )


# ========================================
# Helper Functions
# ========================================

def get_receipt_by_id(db, receipt_id: str) -> Optional[Receipt]:
    """
    Get a receipt by ID.
    
    Args:
        db: Database session
        receipt_id: Receipt UUID
    
    Returns:
        Receipt or None if not found
    """
    return db.query(Receipt).filter_by(id=receipt_id).first()


def get_receipts_by_subject(
    db,
    subject: str,
    limit: int = 100
) -> List[Receipt]:
    """
    Get recent receipts for a subject.
    
    Args:
        db: Database session
        subject: Subject identifier
        limit: Maximum number of receipts to return
    
    Returns:
        List of receipts, newest first
    """
    return (
        db.query(Receipt)
        .filter_by(subject=subject)
        .order_by(Receipt.created_at.desc())
        .limit(limit)
        .all()
    )


def get_receipts_by_decision(
    db,
    decision: DecisionType,
    limit: int = 100
) -> List[Receipt]:
    """
    Get recent receipts by decision type.
    
    Args:
        db: Database session
        decision: Decision type to filter by
        limit: Maximum number of receipts
    
    Returns:
        List of receipts, newest first
    """
    return (
        db.query(Receipt)
        .filter_by(decision=decision.value)
        .order_by(Receipt.created_at.desc())
        .limit(limit)
        .all()
    )