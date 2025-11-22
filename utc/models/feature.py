"""
Feature model for computed queueing metrics.

Features represent time-series metrics computed for each "unit" (route, service, etc.).
Used for predictive queueing and automatic policy escalation.

Why store features?
- Track arrival rate (λ), service rate (μ), utilization (ρ) over time
- Detect trends and anomalies
- Support predictive policy decisions
- Historical analysis and debugging
"""

from typing import Optional, List
from datetime import datetime, UTC

from sqlalchemy import String, Float, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column

from utc.models.base import Base, BaseModel

class Feature(BaseModel, Base):
    """
    Computed queueing metrics per unit.
    
    Attributes:
        id: Auto-incrementing primary key
        ts: Timestamp when metrics were computed
        unit: Unit identifier (e.g., "route:/payments", "service:gateway")
        lambda_est: Estimated arrival rate (requests/hour)
        mu_est: Estimated service rate (capacity to handle requests/hour)
        rho: Utilization ratio (λ/μ), 0.0-1.0
        matched_count: Number of risky events matched
        jailbreak_trend: Trend indicator (e.g., "stable", "rising", "falling")
        created_at: When record was created (from BaseModel)
        updated_at: When record was last modified (from BaseModel)
    
    Queueing Theory Primer:
    - λ (lambda): Arrival rate - how fast requests come in
    - μ (mu): Service rate - how fast we can process them
    - ρ (rho): Utilization = λ/μ
      - ρ < 0.6: System healthy (low load)
      - 0.6 ≤ ρ < 0.9: Medium load (require approvals)
      - ρ ≥ 0.9: System overloaded (read-only mode)
    
    Example:
        feature = Feature(
            ts=datetime.utcnow(),
            unit="route:/payments",
            lambda_est=0.2,  # 0.2 requests/hour
            mu_est=1.0,      # Can handle 1 request/hour
            rho=0.2,         # 20% utilization
            matched_count=5,
            jailbreak_trend="stable"
        )
    """
    
    __tablename__ = "features"
    
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
    # Time & Unit
    # ========================================
    
    ts: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
        comment="Timestamp when metrics were computed"
    )
    
    unit: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
        comment="Unit identifier (e.g., 'route:/payments')"
    )
    
    # ========================================
    # Queueing Metrics
    # ========================================
    
    lambda_est: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Estimated arrival rate (requests/hour)"
    )
    
    mu_est: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Estimated service rate (capacity requests/hour)"
    )
    
    rho: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Utilization ratio (λ/μ), 0.0-1.0"
    )
    
    # ========================================
    # Risk Metrics
    # ========================================
    
    matched_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of risky events matched"
    )
    
    jailbreak_trend: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Trend indicator (e.g., 'stable', 'rising', 'falling')"
    )
    
    # ========================================
    # Indexes
    # ========================================
    
    __table_args__ = (
        Index('ix_features_unit_ts', 'unit', 'ts'),
        Index('ix_features_ts_rho', 'ts', 'rho'),
        {'comment': 'Computed queueing metrics per unit'}
    )
    
    # ========================================
    # Business Logic Methods
    # ========================================
    
    def is_healthy(self) -> bool:
        """
        Check if system is healthy (low utilization).
        
        Returns:
            True if ρ < 0.6
        """
        return self.rho < 0.6
    
    def is_overloaded(self) -> bool:
        """
        Check if system is overloaded (high utilization).
        
        Returns:
            True if ρ ≥ 0.9
        """
        return self.rho >= 0.9
    
    def needs_approval_mode(self) -> bool:
        """
        Check if system should be in approval mode.
        
        Returns:
            True if 0.6 ≤ ρ < 0.9
        """
        return 0.6 <= self.rho < 0.9
    
    def get_protection_level(self) -> str:
        """
        Get recommended protection level based on utilization.
        
        Returns:
            "permissive", "require_approval", or "read_only"
        """
        if self.is_overloaded():
            return "read_only"
        elif self.needs_approval_mode():
            return "require_approval"
        else:
            return "permissive"
    
    # ========================================
    # Validation
    # ========================================
    
    def __init__(self, **kwargs):
        """Initialize Feature with validation."""
        # Auto-set ts if not provided
        if 'ts' not in kwargs:
            kwargs['ts'] = datetime.now(UTC)
        
        super().__init__(**kwargs)
        
        # Validate rho range
        if not 0.0 <= self.rho <= 1.0:
            raise ValueError(f"Rho must be 0.0-1.0, got {self.rho}")
        
        # Validate lambda and mu are non-negative
        if self.lambda_est < 0:
            raise ValueError(f"Lambda must be >= 0, got {self.lambda_est}")
        if self.mu_est <= 0:
            raise ValueError(f"Mu must be > 0, got {self.mu_est}")
    
    # ========================================
    # String Representation
    # ========================================
    
    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return (
            f"<Feature(id={self.id}, "
            f"unit='{self.unit}', "
            f"rho={self.rho:.2f}, "
            f"level='{self.get_protection_level()}')>"
        )
    
    def __str__(self) -> str:
        """Human-readable representation."""
        return (
            f"{self.unit}: ρ={self.rho:.2%} "
            f"(λ={self.lambda_est:.2f}, μ={self.mu_est:.2f}) "
            f"→ {self.get_protection_level()}"
        )


# ========================================
# Helper Functions
# ========================================

def get_latest_feature(db, unit: str) -> Optional[Feature]:
    """
    Get most recent feature for a unit.
    
    Args:
        db: Database session
        unit: Unit identifier
    
    Returns:
        Most recent Feature or None
    """
    return (
        db.query(Feature)
        .filter_by(unit=unit)
        .order_by(Feature.ts.desc())
        .first()
    )


def get_feature_history(
    db,
    unit: str,
    limit: int = 100
) -> List[Feature]:
    """
    Get feature history for a unit.
    
    Args:
        db: Database session
        unit: Unit identifier
        limit: Maximum number of records
    
    Returns:
        List of Features, newest first
    """
    return (
        db.query(Feature)
        .filter_by(unit=unit)
        .order_by(Feature.ts.desc())
        .limit(limit)
        .all()
    )


def get_overloaded_units(db) -> List[Feature]:
    """
    Get all currently overloaded units.
    
    Returns:
        List of Features where ρ ≥ 0.9
    """
    # Get latest feature for each unit
    from sqlalchemy import func
    
    subquery = (
        db.query(
            Feature.unit,
            func.max(Feature.ts).label('max_ts')
        )
        .group_by(Feature.unit)
        .subquery()
    )
    
    latest_features = (
        db.query(Feature)
        .join(
            subquery,
            (Feature.unit == subquery.c.unit) & 
            (Feature.ts == subquery.c.max_ts)
        )
        .filter(Feature.rho >= 0.9)
        .all()
    )
    
    return latest_features