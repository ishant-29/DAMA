"""
Admin API endpoints — system config, market holidays, stock universe.
All write endpoints require admin role.
"""

import csv
import io
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import SystemConfig, MarketHoliday, StockUniverse
from app.auth import get_current_user, User
from app.services.config_service import ConfigService
from app.services.market_calendar import MarketCalendarService
from app.services.stock_universe_service import StockUniverseService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Admin Guard ──────────────────────────────────────────

def require_admin(current_user: User = Depends(get_current_user)):
    """Dependency that checks if the current user is an admin."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# ═══════════════════════════════════════════════════════════
# SYSTEM CONFIG ENDPOINTS
# ═══════════════════════════════════════════════════════════

class ConfigUpdateBody(BaseModel):
    value: str
    reason: Optional[str] = None


@router.get("/config")
def list_all_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns all SystemConfig rows — read-only for any authenticated user."""
    rows = db.query(SystemConfig).order_by(SystemConfig.key).all()
    return [
        {
            "key": r.key,
            "value": r.value,
            "value_type": r.value_type,
            "description": r.description,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            "updated_by": r.updated_by,
        }
        for r in rows
    ]


@router.get("/config/{key}")
def get_single_config(
    key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns a single config value + metadata."""
    row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if not row:
        raise HTTPException(404, f"Config key '{key}' not found")
    return {
        "key": row.key,
        "value": row.value,
        "value_type": row.value_type,
        "description": row.description,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "updated_by": row.updated_by,
        "resolved_value": ConfigService.get(key, db),
    }


@router.put("/config/{key}")
def update_config(
    key: str,
    body: ConfigUpdateBody,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Update a config value — admin only. Validates type before saving."""
    row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if not row:
        raise HTTPException(404, f"Config key '{key}' not found")

    # Validate that the value can be cast to the declared type
    try:
        ConfigService._cast(body.value, row.value_type)
    except Exception:
        raise HTTPException(
            422,
            f"Cannot cast '{body.value}' to type '{row.value_type}'"
        )

    old_value = row.value
    row.value = body.value
    row.updated_at = datetime.now(timezone.utc)
    row.updated_by = admin.username
    db.commit()
    db.refresh(row)

    ConfigService.invalidate_cache(key)

    logger.info(
        f"Config '{key}' changed: {old_value} → {body.value} "
        f"by {admin.username} (reason: {body.reason})"
    )

    return {
        "key": row.key,
        "value": row.value,
        "value_type": row.value_type,
        "old_value": old_value,
        "updated_by": row.updated_by,
        "updated_at": row.updated_at.isoformat(),
    }


@router.post("/config/reload")
def reload_config_cache(
    admin: User = Depends(require_admin),
):
    """Clear entire ConfigService cache — admin only."""
    ConfigService.invalidate_cache()
    return {"status": "ok", "message": "Config cache fully invalidated"}


# ═══════════════════════════════════════════════════════════
# MARKET HOLIDAYS ENDPOINTS
# ═══════════════════════════════════════════════════════════

class HolidayCreateBody(BaseModel):
    date: str  # YYYY-MM-DD
    description: str


@router.get("/market/holidays")
def list_holidays(
    year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all market holidays, optionally filtered by year."""
    holidays = MarketCalendarService.get_holidays(db, year=year)
    return [
        {
            "date": h.date,
            "description": h.description,
            "created_by": h.created_by,
        }
        for h in holidays
    ]


@router.post("/market/holidays")
def add_holiday(
    body: HolidayCreateBody,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Add a market holiday — admin only."""
    # Check duplicate
    existing = db.query(MarketHoliday).filter(MarketHoliday.date == body.date).first()
    if existing:
        raise HTTPException(409, f"Holiday on {body.date} already exists: {existing.description}")

    holiday = MarketHoliday(
        date=body.date,
        description=body.description,
        created_by=admin.username,
    )
    db.add(holiday)
    db.commit()
    db.refresh(holiday)

    return {"date": holiday.date, "description": holiday.description, "status": "created"}


@router.delete("/market/holidays/{date}")
def delete_holiday(
    date: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Remove a market holiday — admin only."""
    holiday = db.query(MarketHoliday).filter(MarketHoliday.date == date).first()
    if not holiday:
        raise HTTPException(404, f"No holiday found on {date}")

    db.delete(holiday)
    db.commit()
    return {"date": date, "status": "deleted"}


# ═══════════════════════════════════════════════════════════
# STOCK UNIVERSE ENDPOINTS
# ═══════════════════════════════════════════════════════════

class StockCreateBody(BaseModel):
    symbol: str
    name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    index_name: str = "NIFTY500"


class StockUpdateBody(BaseModel):
    name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    index_name: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/stocks")
def list_stocks(
    sector: Optional[str] = Query(None),
    index_name: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(True),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List stocks with optional filters — paginated."""
    query = db.query(StockUniverse)
    if sector:
        query = query.filter(StockUniverse.sector == sector)
    if index_name:
        query = query.filter(StockUniverse.index_name == index_name)
    if is_active is not None:
        query = query.filter(StockUniverse.is_active == is_active)

    total = query.count()
    rows = query.order_by(StockUniverse.symbol).offset(skip).limit(limit).all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "stocks": [
            {
                "symbol": r.symbol,
                "name": r.name,
                "sector": r.sector,
                "industry": r.industry,
                "index_name": r.index_name,
                "is_active": r.is_active,
            }
            for r in rows
        ],
    }


@router.post("/stocks")
def add_stock(
    body: StockCreateBody,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Add a new stock — admin only."""
    existing = db.query(StockUniverse).filter(StockUniverse.symbol == body.symbol).first()
    if existing:
        raise HTTPException(409, f"Stock '{body.symbol}' already exists")

    stock = StockUniverse(
        symbol=body.symbol,
        name=body.name,
        sector=body.sector,
        industry=body.industry,
        index_name=body.index_name,
    )
    db.add(stock)
    db.commit()
    db.refresh(stock)

    StockUniverseService.reload(db)
    return {"symbol": stock.symbol, "status": "created"}


@router.put("/stocks/{symbol}")
def update_stock(
    symbol: str,
    body: StockUpdateBody,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Update stock metadata or deactivate — admin only."""
    stock = db.query(StockUniverse).filter(StockUniverse.symbol == symbol).first()
    if not stock:
        raise HTTPException(404, f"Stock '{symbol}' not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(stock, field, value)

    db.commit()
    db.refresh(stock)

    StockUniverseService.reload(db)
    return {"symbol": stock.symbol, "status": "updated"}


@router.post("/stocks/reload")
def reload_stock_cache(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Force StockUniverseService cache reload — admin only."""
    StockUniverseService.reload(db)
    return {"status": "ok", "message": "Stock universe cache reloaded"}


@router.post("/stocks/import-csv")
async def import_stocks_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Upload CSV to upsert stocks — admin only. CSV must have 'symbol' column."""
    content = await file.read()
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))

    created, updated = 0, 0
    for row in reader:
        symbol = row.get("symbol", "").strip()
        if not symbol:
            continue

        existing = db.query(StockUniverse).filter(StockUniverse.symbol == symbol).first()
        if existing:
            existing.name = row.get("company_name", row.get("name", existing.name))
            existing.sector = row.get("sector", existing.sector)
            existing.industry = row.get("industry", existing.industry)
            existing.is_active = True
            updated += 1
        else:
            stock = StockUniverse(
                symbol=symbol,
                name=row.get("company_name", row.get("name", "")),
                sector=row.get("sector", ""),
                industry=row.get("industry", ""),
                index_name=row.get("index_name", "NIFTY500"),
            )
            db.add(stock)
            created += 1

    db.commit()
    StockUniverseService.reload(db)

    return {"status": "ok", "created": created, "updated": updated}
