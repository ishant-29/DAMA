"""
Stock Universe Service — DB-backed, cached stock list.
Replaces CSV-only symbol lists with a queryable, reloadable service.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.db.models import StockUniverse

logger = logging.getLogger(__name__)


class StockUniverseService:
    """Cached stock universe from the stock_universe table."""

    _cache: dict = {}
    _loaded_at: Optional[datetime] = None
    _TTL_seconds: int = 3600  # reload from DB hourly

    @classmethod
    def _load(cls, db: Session):
        """Load all active stocks from DB into structured cache."""
        rows = (
            db.query(StockUniverse)
            .filter(StockUniverse.is_active == True)
            .all()
        )

        all_symbols = []
        by_sector: dict[str, list[str]] = {}
        by_index: dict[str, list[str]] = {}

        for row in rows:
            all_symbols.append(row.symbol)

            if row.sector:
                by_sector.setdefault(row.sector, []).append(row.symbol)
            if row.index_name:
                by_index.setdefault(row.index_name, []).append(row.symbol)

        cls._cache = {
            "all": all_symbols,
            "by_sector": by_sector,
            "by_index": by_index,
        }
        cls._loaded_at = datetime.now(timezone.utc)
        logger.info(f"StockUniverse loaded: {len(all_symbols)} active symbols, "
                     f"{len(by_sector)} sectors, {len(by_index)} indices")

    @classmethod
    def _ensure_loaded(cls, db: Session):
        """Lazy-load if cache is empty or expired."""
        if (cls._loaded_at is None or
                (datetime.now(timezone.utc) - cls._loaded_at).total_seconds() > cls._TTL_seconds):
            cls._load(db)

    @classmethod
    def get_all_symbols(cls, db: Session) -> list[str]:
        cls._ensure_loaded(db)
        return cls._cache.get("all", [])

    @classmethod
    def get_by_sector(cls, sector: str, db: Session) -> list[str]:
        cls._ensure_loaded(db)
        return cls._cache.get("by_sector", {}).get(sector, [])

    @classmethod
    def get_by_index(cls, index: str, db: Session) -> list[str]:
        cls._ensure_loaded(db)
        return cls._cache.get("by_index", {}).get(index, [])

    @classmethod
    def get_sectors(cls, db: Session) -> list[str]:
        cls._ensure_loaded(db)
        return sorted(cls._cache.get("by_sector", {}).keys())

    @classmethod
    def get_indices(cls, db: Session) -> list[str]:
        cls._ensure_loaded(db)
        return sorted(cls._cache.get("by_index", {}).keys())

    @classmethod
    def reload(cls, db: Session):
        """Force cache reload from DB."""
        cls._loaded_at = None
        cls._load(db)
