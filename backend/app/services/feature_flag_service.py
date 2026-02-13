"""
Feature flag service for tenant overrides.
"""

from sqlalchemy.orm import Session

from app.models.feature_flag import FeatureFlag


class FeatureFlagService:
    """Service for feature flag operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_flags_for_tenant(self, tenant_id) -> dict:
        """Return tenant-level feature flag overrides."""
        flags = self.db.query(FeatureFlag).filter(
            FeatureFlag.tenant_id == tenant_id
        ).all()
        return {flag.key: flag.enabled for flag in flags}
