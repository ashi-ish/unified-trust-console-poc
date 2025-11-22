"""
Event model for external trust/risk intelligence.

Events represent external security/risk information from sources like:
- Security news feeds (CVE databases, vendor advisories)
- Threat intelligence platforms
- Manual submissions from security team
- Third-party risk APIs

Why store events?
- Trust Data Exchange (TDX) ingests and normalizes them
- Triggers automatic policy changes based on external threats
- Audit trail of what external factors influenced decisions
- Feature extraction for ML/analytics
"""

from typing import Optional, List
from datetime import datetime, UTC

from sqlalchemy import String, Text, Float, Integer, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from utc.models.base import Base, BaseModel


class Event(BaseModel, Base):
    """
    External trust/risk event.
    
    Attributes:
        id: Auto-incrementing primary key
        source: Where event came from (e.g., "nvd.nist.gov", "manual")
        when_seen: When we ingested this event
        event_time: When the event actually occurred (may be in the past)
        topic: Category (e.g., "cve", "incident", "policy-update")
        severity: Severity level (e.g., "critical", "high", "medium", "low")
        confidence: Confidence score 0.0-1.0 (how reliable is this?)
        entities_json: Affected entities (JSON array: ["service-A", "api-gateway"])
        link: URL to original source
        hash: Content hash (prevents duplicate ingestion)
        summary: Human-readable description
        created_at: When record was created (from BaseModel)
        updated_at: When record was last modified (from BaseModel)
    
    Example:
        event = Event(
            source="nvd.nist.gov",
            event_time=datetime(2024, 1, 15, 10, 30),
            topic="cve",
            severity="critical",
            confidence=0.95,
            entities=["openssl", "tls"],
            link="https://nvd.nist.gov/vuln/detail/CVE-2024-0001",
            hash="sha256:abc123...",
            summary="Critical TLS vulnerability in OpenSSL 3.x"
        )
    """
    
    __tablename__ = "events"
    
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
    # Source Information
    # ========================================
    
    source: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
        comment="Event source (e.g., 'nvd.nist.gov', 'manual')"
    )
    
    when_seen: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
        comment="When we ingested this event (our timestamp)"
    )
    
    event_time: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
        comment="When the event actually occurred (source timestamp)"
    )
    
    # ========================================
    # Event Classification
    # ========================================
    
    topic: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Event category (e.g., 'cve', 'incident', 'policy-update')"
    )
    
    severity: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Severity level (e.g., 'critical', 'high', 'medium', 'low')"
    )
    
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
        comment="Confidence score 0.0-1.0 (how reliable is this event?)"
    )
    
    # ========================================
    # Event Details
    # ========================================
    
    entities_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
        comment="Affected entities (JSON array of strings)"
    )
    
    link: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="URL to original source/details"
    )
    
    hash: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,  # Prevent duplicate ingestion
        index=True,
        comment="Content hash (prevents duplicates)"
    )
    
    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Human-readable event description"
    )
    
    # ========================================
    # Indexes & Constraints
    # ========================================
    
    __table_args__ = (
        Index('ix_events_source_event_time', 'source', 'event_time'),
        Index('ix_events_topic_severity', 'topic', 'severity'),
        UniqueConstraint('hash', name='uq_events_hash'),
        {'comment': 'External trust/risk events'}
    )
    
    # ========================================
    # Property Accessors (JSON)
    # ========================================
    
    @property
    def entities(self) -> List[str]:
        """
        Get entities as Python list.
        
        Returns:
            List of entity identifiers
        """
        import json
        try:
            return json.loads(self.entities_json)
        except (json.JSONDecodeError, TypeError):
            return []
    
    @entities.setter
    def entities(self, value: List[str]) -> None:
        """Set entities from Python list."""
        import json
        self.entities_json = json.dumps(value)
    
    # ========================================
    # Business Logic Methods
    # ========================================
    
    def is_critical(self) -> bool:
        """Check if event is critical severity."""
        return self.severity.lower() == "critical"
    
    def is_high_confidence(self, threshold: float = 0.8) -> bool:
        """
        Check if event has high confidence.
        
        Args:
            threshold: Minimum confidence (default 0.8)
        
        Returns:
            True if confidence >= threshold
        """
        return self.confidence >= threshold
    
    def should_trigger_policy_change(self) -> bool:
        """
        Determine if event should trigger automatic policy change.
        
        Logic: Critical events with high confidence
        
        Returns:
            True if should trigger policy change
        """
        return self.is_critical() and self.is_high_confidence()
    
    # ========================================
    # Validation
    # ========================================
    
    def __init__(self, **kwargs):
        """Initialize Event with validation."""
        # Handle entities list → JSON
        if 'entities' in kwargs and 'entities_json' not in kwargs:
            entities_list = kwargs.pop('entities')
            import json
            kwargs['entities_json'] = json.dumps(entities_list)
        
        # Auto-set when_seen if not provided
        if 'when_seen' not in kwargs:
            kwargs['when_seen'] = datetime.now(UTC)
        
        super().__init__(**kwargs)
        
        # Validate confidence range
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be 0.0-1.0, got {self.confidence}")
    
    # ========================================
    # String Representation
    # ========================================
    
    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return (
            f"<Event(id={self.id}, "
            f"source='{self.source}', "
            f"topic='{self.topic}', "
            f"severity='{self.severity}')>"
        )
    
    def __str__(self) -> str:
        """Human-readable representation."""
        return (
            f"[{self.severity.upper()}] {self.topic} from {self.source}: "
            f"{self.summary[:50]}..."
        )


# ========================================
# Helper Functions
# ========================================

def get_event_by_hash(db, hash_value: str) -> Optional[Event]:
    """
    Get event by hash (check if already ingested).
    
    Args:
        db: Database session
        hash_value: Event content hash
    
    Returns:
        Event or None if not found
    """
    return db.query(Event).filter_by(hash=hash_value).first()


def get_recent_events(
    db,
    hours: int = 24,
    min_severity: str = "medium"
) -> List[Event]:
    """
    Get recent high-priority events.
    
    Args:
        db: Database session
        hours: Look back this many hours
        min_severity: Minimum severity to include
    
    Returns:
        List of events, newest first
    """
    from datetime import timedelta
    
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    severity_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    min_level = severity_order.get(min_severity.lower(), 0)
    
    events = (
        db.query(Event)
        .filter(Event.when_seen >= cutoff)
        .order_by(Event.when_seen.desc())
        .all()
    )
    
    # Filter by severity (can't do in SQL easily)
    return [
        e for e in events
        if severity_order.get(e.severity.lower(), 0) >= min_level
    ]