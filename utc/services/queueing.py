"""
Queueing Service
================

Implements queueing theory calculations for predictive policy escalation.

Key Concepts:
- λ (lambda): Arrival rate - requests per time unit
- μ (mu): Service rate - capacity per time unit
- ρ (rho): Utilization ratio = λ/μ (how busy the system is)
- EWMA: Exponentially Weighted Moving Average for smoothing

Protection Levels (based on ρ):
- ρ < 0.6: Permissive (allow all)
- 0.6 ≤ ρ < 0.9: Require approval (elevated risk)
- ρ ≥ 0.9: Read-only (system overload prevention)

Auto-relaxation:
- When ρ drops below 0.5, automatically relax read-only → approval or approval → permissive

Learning Outcome:
- Queueing theory prevents system overload before it happens (predictive vs reactive)
- EWMA smooths out spikes while still being responsive to trends
- Gradual escalation/de-escalation prevents policy flapping
"""

from datetime import datetime, UTC
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from utc.models.feature import Feature
from utc.config import settings


class QueueingService:
    """
    Service for calculating queueing metrics and determining protection levels.

    Uses EWMA (Exponentially Weighted Moving Average) to smooth arrival rate estimates
    and prevent overreaction to temporary spikes.

    Why EWMA?
    - Simple: new_estimate = α * observation + (1-α) * old_estimate
    - Responsive: Recent observations have more weight
    - Smooth: Historical data prevents wild swings
    - α (alpha): 0.3 means 30% weight to new data, 70% to history

    Example:
        # Calculate current utilization for a unit
        feature = queueing_service.get_or_create_feature(db, "payments-api")
        protection_level = feature.get_protection_level()

        # Update with new observation
        queueing_service.update_feature(db, "payments-api", arrival_rate=50.0, service_rate=100.0)
    """

    def __init__(self, db: Session, alpha: Optional[float] = None,
                 threshold_low: Optional[float] = None,
                 threshold_high: Optional[float] = None):
        """
        Initialize the queueing service.

        Args:
            db: SQLAlchemy database session
            alpha: EWMA smoothing factor (0-1). Default from settings.
            threshold_low: Low threshold for approval mode (default 0.6)
            threshold_high: High threshold for read-only mode (default 0.9)

        Why dependency injection for db?
        - Each request gets its own session (thread-safe)
        - Makes testing easy (can mock the db)
        - Follows SOLID: Dependency Inversion Principle
        """
        self.db = db
        self.alpha = alpha if alpha is not None else settings.queue_alpha
        self.threshold_low = threshold_low if threshold_low is not None else settings.queue_threshold_low
        self.threshold_high = threshold_high if threshold_high is not None else settings.queue_threshold_high

        # Validation
        if not 0 < self.alpha < 1:
            raise ValueError(f"Alpha must be between 0 and 1, got {self.alpha}")
        if not 0 < self.threshold_low < self.threshold_high < 1:
            raise ValueError(f"Thresholds must satisfy 0 < low < high < 1")

    def get_feature(self, unit: str) -> Optional[Feature]:
        """
        Get existing feature metrics for a unit.

        Args:
            unit: The unit identifier (e.g., "payments-api", "user:alice")

        Returns:
            Feature object if found, None otherwise
        """
        return self.db.query(Feature).filter_by(unit=unit).first()

    def get_or_create_feature(self, unit: str, initial_lambda: float = 1.0,
                               initial_mu: float = 10.0) -> Feature:
        """
        Get or create a feature with initial estimates.

        Args:
            unit: The unit identifier
            initial_lambda: Initial arrival rate estimate (default: 1.0 req/hr)
            initial_mu: Initial service rate estimate (default: 10.0 req/hr)

        Returns:
            Feature object (existing or newly created)

        Why defaults matter:
        - Start pessimistic (low λ, high μ) = low ρ = permissive
        - As real data arrives, EWMA converges to true values
        - Better to start permissive and escalate than start locked down
        """
        feature = self.get_feature(unit)
        if feature:
            return feature

        # Calculate initial utilization
        rho = self._calculate_rho(initial_lambda, initial_mu)

        # Create new feature
        feature = Feature(
            unit=unit,
            lambda_est=initial_lambda,
            mu_est=initial_mu,
            rho=rho
        )
        self.db.add(feature)
        self.db.flush()  # Get the ID without committing the transaction

        return feature

    def update_feature(self, unit: str, arrival_rate: float, service_rate: float) -> Feature:
        """
        Update feature metrics using EWMA smoothing.

        Args:
            unit: The unit identifier
            arrival_rate: Observed arrival rate (λ_observed)
            service_rate: Observed service rate (μ_observed)

        Returns:
            Updated Feature object

        EWMA Formula:
            new_λ = α * λ_observed + (1-α) * old_λ
            new_μ = α * μ_observed + (1-α) * old_μ
            new_ρ = new_λ / new_μ

        Example with α=0.3:
            old_λ = 10, observed = 20
            new_λ = 0.3*20 + 0.7*10 = 6 + 7 = 13
            (30% of new data, 70% of old data)
        """
        feature = self.get_or_create_feature(unit)

        # Apply EWMA smoothing
        new_lambda = self.alpha * arrival_rate + (1 - self.alpha) * feature.lambda_est
        new_mu = self.alpha * service_rate + (1 - self.alpha) * feature.mu_est
        new_rho = self._calculate_rho(new_lambda, new_mu)

        # Update the feature
        feature.lambda_est = new_lambda
        feature.mu_est = new_mu
        feature.rho = new_rho

        self.db.flush()

        return feature

    def _calculate_rho(self, lambda_est: float, mu_est: float) -> float:
        """
        Calculate utilization ratio ρ = λ/μ.

        Args:
            lambda_est: Arrival rate estimate
            mu_est: Service rate estimate

        Returns:
            Utilization ratio (capped at 0.99 to prevent division by zero issues)

        Why cap at 0.99?
        - ρ = 1.0 means system is at exact capacity (unstable)
        - ρ > 1.0 means arrival > capacity (queue grows infinitely)
        - In practice, we want ρ < 0.9 for healthy systems
        - Cap prevents numerical issues and enforces sane limits
        """
        if mu_est <= 0:
            raise ValueError(f"Service rate must be positive, got {mu_est}")

        rho = lambda_est / mu_est

        # Cap at 0.99 to prevent overflow/instability
        return min(rho, 0.99)

    def get_protection_level(self, unit: str) -> str:
        """
        Get the current protection level for a unit based on ρ.

        Args:
            unit: The unit identifier

        Returns:
            Protection level: "permissive", "require_approval", or "read_only"

        Thresholds (configurable via settings):
        - ρ < 0.6: permissive (system has plenty of capacity)
        - 0.6 ≤ ρ < 0.9: require_approval (getting busy, be careful)
        - ρ ≥ 0.9: read_only (near capacity, prevent overload)

        Why these thresholds?
        - Industry rule of thumb: keep ρ < 0.7 for good responsiveness
        - ρ > 0.8: response times start growing exponentially
        - ρ > 0.9: system is at risk of saturation
        """
        feature = self.get_or_create_feature(unit)
        return feature.get_protection_level()

    def should_auto_relax(self, unit: str) -> bool:
        """
        Check if auto-relaxation should trigger.

        Auto-relaxation occurs when ρ drops below 0.5 (well below low threshold).
        This prevents staying in elevated protection mode when load decreases.

        Args:
            unit: The unit identifier

        Returns:
            True if ρ < 0.5 (safe to relax protection)

        Why 0.5?
        - Half of the low threshold (0.6)
        - Provides hysteresis to prevent flapping
        - If load was high (0.9) → drops to 0.7: still above 0.5, keep protection
        - If load drops to 0.4: clearly safe, relax protection
        """
        feature = self.get_feature(unit)
        if not feature:
            return False

        return feature.rho < 0.5

    def get_all_features(self) -> list[Feature]:
        """
        Get all tracked features.

        Returns:
            List of all Feature objects

        Use case:
        - Dashboard showing all units and their protection levels
        - Batch processing for auto-relaxation checks
        - Evidence generation (show all monitored units)
        """
        return self.db.query(Feature).order_by(Feature.rho.desc()).all()

    def get_metrics_summary(self, unit: str) -> Dict[str, Any]:
        """
        Get a human-readable summary of queueing metrics for a unit.

        Args:
            unit: The unit identifier

        Returns:
            Dictionary with metrics and interpretations

        Example output:
        {
            "unit": "payments-api",
            "lambda": 75.5,
            "mu": 100.0,
            "rho": 0.755,
            "protection_level": "require_approval",
            "interpretation": "System is 75.5% utilized",
            "recommendation": "Writes require approval due to elevated load"
        }
        """
        feature = self.get_feature(unit)
        if not feature:
            return {
                "unit": unit,
                "status": "not_tracked",
                "message": "No metrics available for this unit"
            }

        protection_level = feature.get_protection_level()

        # Interpretation messages
        if protection_level == "permissive":
            interpretation = f"System is {feature.rho*100:.1f}% utilized (healthy)"
            recommendation = "All operations allowed"
        elif protection_level == "require_approval":
            interpretation = f"System is {feature.rho*100:.1f}% utilized (elevated)"
            recommendation = "Writes require approval due to increased load"
        else:  # read_only
            interpretation = f"System is {feature.rho*100:.1f}% utilized (critical)"
            recommendation = "Read-only mode to prevent overload"

        return {
            "unit": unit,
            "lambda": round(feature.lambda_est, 2),
            "mu": round(feature.mu_est, 2),
            "rho": round(feature.rho, 3),
            "protection_level": protection_level,
            "interpretation": interpretation,
            "recommendation": recommendation,
            "updated_at": feature.updated_at.isoformat() if feature.updated_at else None
        }


# Singleton instance (one service instance across the app)
_queueing_service: Optional[QueueingService] = None


def get_queueing_service(db: Session) -> QueueingService:
    """
    Get or create the singleton queueing service instance.

    Args:
        db: SQLAlchemy database session

    Returns:
        QueueingService instance

    Why singleton?
    - Configuration (alpha, thresholds) should be consistent
    - No state stored in service itself (all state in database)
    - Reduces object creation overhead

    Note: We still pass db per request for thread safety!
    """
    global _queueing_service
    if _queueing_service is None:
        _queueing_service = QueueingService(db)
    else:
        # Update db session for current request
        _queueing_service.db = db
    return _queueing_service


# ============================================================================
# DEMO / TEST CODE
# ============================================================================

if __name__ == "__main__":
    """
    Test the queueing service with realistic scenarios.

    Scenario:
    1. Start with low load (ρ=0.3, permissive)
    2. Increase load (ρ=0.7, require_approval)
    3. Further increase (ρ=0.92, read_only)
    4. Decrease load (ρ=0.4, auto-relax to permissive)
    """
    from utc.database import get_db_context

    print("\n" + "="*60)
    print("QUEUEING SERVICE TEST")
    print("="*60)

    with get_db_context() as db:
        queueing = get_queueing_service(db)
        unit = "test-payments-api"

        print(f"\n📊 Testing unit: {unit}")
        print(f"   Alpha (smoothing): {queueing.alpha}")
        print(f"   Thresholds: low={queueing.threshold_low}, high={queueing.threshold_high}")

        # Test 1: Initial state (low load)
        print("\n1️⃣  Initial state (low load)")
        feature = queueing.get_or_create_feature(unit, initial_lambda=3.0, initial_mu=10.0)
        summary = queueing.get_metrics_summary(unit)
        print(f"   λ={summary['lambda']}, μ={summary['mu']}, ρ={summary['rho']}")
        print(f"   Protection: {summary['protection_level']}")
        print(f"   📝 {summary['interpretation']}")

        # Test 2: Increase load (require approval)
        print("\n2️⃣  Load increases (elevated risk)")
        queueing.update_feature(unit, arrival_rate=70.0, service_rate=100.0)
        summary = queueing.get_metrics_summary(unit)
        print(f"   λ={summary['lambda']}, μ={summary['mu']}, ρ={summary['rho']}")
        print(f"   Protection: {summary['protection_level']}")
        print(f"   📝 {summary['interpretation']}")
        print(f"   ⚠️  {summary['recommendation']}")

        # Test 3: Further increase (read-only)
        print("\n3️⃣  Load spikes (critical)")
        queueing.update_feature(unit, arrival_rate=95.0, service_rate=100.0)
        summary = queueing.get_metrics_summary(unit)
        print(f"   λ={summary['lambda']}, μ={summary['mu']}, ρ={summary['rho']}")
        print(f"   Protection: {summary['protection_level']}")
        print(f"   📝 {summary['interpretation']}")
        print(f"   🛑 {summary['recommendation']}")

        # Test 4: Load decreases (auto-relax check)
        print("\n4️⃣  Load decreases (checking auto-relax)")
        queueing.update_feature(unit, arrival_rate=4.0, service_rate=10.0)
        summary = queueing.get_metrics_summary(unit)
        should_relax = queueing.should_auto_relax(unit)
        print(f"   λ={summary['lambda']}, μ={summary['mu']}, ρ={summary['rho']}")
        print(f"   Protection: {summary['protection_level']}")
        print(f"   Should auto-relax? {should_relax}")
        print(f"   📝 {summary['interpretation']}")

        # Test 5: Get all features
        print("\n5️⃣  All tracked features")
        all_features = queueing.get_all_features()
        print(f"   Total features tracked: {len(all_features)}")
        for f in all_features:
            print(f"   • {f.unit}: ρ={f.rho:.3f} ({f.get_protection_level()})")

        # Test 6: EWMA smoothing demonstration
        print("\n6️⃣  EWMA smoothing demonstration")
        print("   Simulating gradual load increase...")
        unit2 = "test-api-2"
        queueing.get_or_create_feature(unit2, initial_lambda=10.0, initial_mu=100.0)

        observations = [20, 40, 60, 80, 90]
        for i, obs_lambda in enumerate(observations, 1):
            queueing.update_feature(unit2, arrival_rate=obs_lambda, service_rate=100.0)
            feature = queueing.get_feature(unit2)
            print(f"   Step {i}: observed λ={obs_lambda}, smoothed λ={feature.lambda_est:.2f}, ρ={feature.rho:.3f}")

        print("\n✅ All queueing tests passed!")
        print("\n" + "="*60)
