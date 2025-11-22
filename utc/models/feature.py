"""
Feature Model
=============

Stores queueing metrics for predictive policy escalation.
"""

from sqlalchemy import Integer, String, Float, Index
from sqlalchemy.orm import Mapped, mapped_column

from utc.models.base import Base, BaseModel
from utc.config import settings


class Feature(BaseModel, Base):
    """
    Feature model for queueing theory metrics.

    Tracks arrival rate (λ), service rate (μ), and utilization (ρ) for each unit.
    """

    __tablename__ = "features"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit: Mapped[str] = mapped_column(String(200), nullable=False, index=True, unique=True)
    lambda_est: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    mu_est: Mapped[float] = mapped_column(Float, nullable=False, default=10.0)
    rho: Mapped[float] = mapped_column(Float, nullable=False, default=0.1)

    __table_args__ = (
        Index("idx_features_rho", "rho"),
    )

    def is_critical(self) -> bool:
        """Check if utilization is at critical level (>= high threshold)."""
        return self.rho >= settings.queue_threshold_high

    def is_elevated(self) -> bool:
        """Check if utilization is at elevated level (>= low threshold)."""
        return self.rho >= settings.queue_threshold_low

    def get_protection_level(self) -> str:
        """
        Get the protection level based on utilization.

        Returns:
            "read_only" if ρ >= high threshold
            "require_approval" if low <= ρ < high threshold
            "permissive" if ρ < low threshold
        """
        if self.is_critical():
            return "read_only"
        elif self.is_elevated():
            return "require_approval"
        else:
            return "permissive"

    def __repr__(self) -> str:
        return f"<Feature(unit='{self.unit}', λ={self.lambda_est:.2f}, μ={self.mu_est:.2f}, ρ={self.rho:.3f})>"
