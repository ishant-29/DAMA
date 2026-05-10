"""
Per-user trading settings service.
Provides get_or_create, update (with range validation), and reset.
"""

import logging
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.db.models import UserSettings
from app.core.config import settings

logger = logging.getLogger(__name__)

# Validation ranges: (min, max) inclusive
_RANGES = {
    "stop_loss_pct":     (0.01, 0.30),
    "take_profit_pct":   (0.01, 1.00),
    "position_size_pct": (0.005, 0.25),
    "initial_capital":   (1_000, 10_000_000),
    "min_confidence":    (0.50, 0.99),
    "max_positions":     (1, 50),
    "kelly_fraction":    (0.10, 1.00),
    "commission_rate":   (0.0, 0.01),
}


class UserSettingsService:

    @staticmethod
    def get_or_create(user_id: int, db: Session) -> UserSettings:
        """Retrieve existing settings or create with system defaults."""
        row = (
            db.query(UserSettings)
            .filter(UserSettings.user_id == user_id)
            .first()
        )
        if row:
            return row

        # Create with system defaults from settings
        row = UserSettings(
            user_id=user_id,
            stop_loss_pct=getattr(settings, "BACKTEST_DEFAULT_STOP_LOSS", 0.05),
            take_profit_pct=getattr(settings, "BACKTEST_DEFAULT_TAKE_PROFIT", 0.10),
            position_size_pct=getattr(settings, "BACKTEST_DEFAULT_POSITION_SIZE", 0.10),
            initial_capital=getattr(settings, "BACKTEST_DEFAULT_INITIAL_CAPITAL", 1_000_000.0),
            min_confidence=getattr(settings, "ML_CONFIDENCE_THRESHOLD", 0.60),
            max_positions=getattr(settings, "PAPER_MAX_POSITIONS", 5),
            kelly_fraction=0.50,
            commission_rate=0.001,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        logger.info(f"Created default UserSettings for user_id={user_id}")
        return row

    @staticmethod
    def update(user_id: int, updates: dict, db: Session) -> UserSettings:
        """Update user settings with range validation."""
        row = (
            db.query(UserSettings)
            .filter(UserSettings.user_id == user_id)
            .first()
        )
        if not row:
            # Auto-create first
            row = UserSettingsService.get_or_create(user_id, db)

        errors = []
        for field, value in updates.items():
            if field not in _RANGES:
                continue
            lo, hi = _RANGES[field]
            if not (lo <= value <= hi):
                errors.append(f"{field} must be between {lo} and {hi}, got {value}")

        if errors:
            raise HTTPException(status_code=422, detail="; ".join(errors))

        for field, value in updates.items():
            if hasattr(row, field) and field in _RANGES:
                setattr(row, field, value)

        db.commit()
        db.refresh(row)
        logger.info(f"Updated UserSettings for user_id={user_id}: {list(updates.keys())}")
        return row

    @staticmethod
    def reset(user_id: int, db: Session) -> UserSettings:
        """Delete existing settings so next get_or_create returns fresh defaults."""
        row = (
            db.query(UserSettings)
            .filter(UserSettings.user_id == user_id)
            .first()
        )
        if row:
            db.delete(row)
            db.commit()
            logger.info(f"Reset UserSettings for user_id={user_id}")

        return UserSettingsService.get_or_create(user_id, db)
