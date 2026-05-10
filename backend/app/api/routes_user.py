"""
User settings API — per-user trading parameter management.
"""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth import get_current_user, User
from app.services.user_settings_service import UserSettingsService

router = APIRouter(prefix="/user", tags=["user"])


class UserSettingsUpdate(BaseModel):
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    position_size_pct: Optional[float] = None
    initial_capital: Optional[float] = None
    min_confidence: Optional[float] = None
    max_positions: Optional[int] = None
    kelly_fraction: Optional[float] = None
    commission_rate: Optional[float] = None


def _serialize(s):
    return {
        "user_id": s.user_id,
        "stop_loss_pct": s.stop_loss_pct,
        "take_profit_pct": s.take_profit_pct,
        "position_size_pct": s.position_size_pct,
        "initial_capital": s.initial_capital,
        "min_confidence": s.min_confidence,
        "max_positions": s.max_positions,
        "kelly_fraction": s.kelly_fraction,
        "commission_rate": s.commission_rate,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


@router.get("/settings")
def get_user_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns trading settings for current user (creates defaults if first time)."""
    settings = UserSettingsService.get_or_create(current_user.id, db)
    return _serialize(settings)


@router.put("/settings")
def update_user_settings(
    body: UserSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update trading settings — validates ranges (422 if out of bounds)."""
    updates = body.model_dump(exclude_none=True)
    if not updates:
        settings = UserSettingsService.get_or_create(current_user.id, db)
        return _serialize(settings)

    settings = UserSettingsService.update(current_user.id, updates, db)
    return _serialize(settings)


@router.delete("/settings")
def reset_user_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reset all trading settings to system defaults."""
    settings = UserSettingsService.reset(current_user.id, db)
    return {"status": "reset", **_serialize(settings)}
