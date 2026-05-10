"""
Runtime Configuration Service — cached key-value config from DB.
Fallback chain: cache → DB → settings.* → provided default.
"""

import logging
from typing import Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.db.models import SystemConfig
from app.core.config import settings

logger = logging.getLogger(__name__)


class ConfigService:
    """Reads runtime config from system_config table with in-memory cache."""

    _cache: dict[str, dict] = {}
    _loaded: bool = False

    # ── Read ──────────────────────────────────────────

    @classmethod
    def get(cls, key: str, db: Session, fallback: Any = None) -> Any:
        """
        Resolve a config value with fallback chain:
        1. In-memory cache
        2. DB (system_config table)
        3. Matching settings.* attribute
        4. Provided fallback
        """
        # 1. Cache hit
        if key in cls._cache:
            return cls._cast(cls._cache[key]["value"], cls._cache[key]["value_type"])

        # 2. DB lookup
        row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
        if row:
            cls._cache[key] = {"value": row.value, "value_type": row.value_type}
            return cls._cast(row.value, row.value_type)

        # 3. settings.* fallback
        if hasattr(settings, key):
            return getattr(settings, key)

        # 4. Provided fallback
        return fallback

    @classmethod
    def get_float(cls, key: str, db: Session, fallback: float = 0.0) -> float:
        val = cls.get(key, db, fallback=fallback)
        try:
            return float(val)
        except (TypeError, ValueError):
            return fallback

    @classmethod
    def get_int(cls, key: str, db: Session, fallback: int = 0) -> int:
        val = cls.get(key, db, fallback=fallback)
        try:
            return int(float(val))
        except (TypeError, ValueError):
            return fallback

    @classmethod
    def get_str(cls, key: str, db: Session, fallback: str = "") -> str:
        val = cls.get(key, db, fallback=fallback)
        return str(val) if val is not None else fallback

    @classmethod
    def get_bool(cls, key: str, db: Session, fallback: bool = False) -> bool:
        val = cls.get(key, db, fallback=fallback)
        if isinstance(val, bool):
            return val
        return str(val).lower() in ("true", "1", "yes")

    # ── Write ─────────────────────────────────────────

    @classmethod
    def set(cls, key: str, value: str, db: Session,
            updated_by: str = "system") -> SystemConfig:
        """Update or create a config key in the DB and invalidate cache."""
        row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
        if row:
            old_value = row.value
            row.value = value
            row.updated_at = datetime.now(timezone.utc)
            row.updated_by = updated_by
            logger.info(f"Config '{key}' changed: {old_value} → {value} by {updated_by}")
        else:
            row = SystemConfig(
                key=key, value=value, value_type="str",
                updated_by=updated_by,
            )
            db.add(row)
            logger.info(f"Config '{key}' created with value '{value}' by {updated_by}")

        db.commit()
        db.refresh(row)

        # Invalidate cache for this key
        cls.invalidate_cache(key)
        return row

    # ── Cache Management ──────────────────────────────

    @classmethod
    def invalidate_cache(cls, key: Optional[str] = None):
        """Clear cache for a specific key, or entire cache if key=None."""
        if key is None:
            cls._cache.clear()
            cls._loaded = False
            logger.info("ConfigService cache fully invalidated")
        else:
            cls._cache.pop(key, None)
            logger.debug(f"ConfigService cache invalidated for '{key}'")

    @classmethod
    def load_all(cls, db: Session) -> dict[str, Any]:
        """Load all config keys from DB into cache. Returns dict of key→value."""
        rows = db.query(SystemConfig).all()
        result = {}
        for row in rows:
            cls._cache[row.key] = {"value": row.value, "value_type": row.value_type}
            result[row.key] = cls._cast(row.value, row.value_type)
        cls._loaded = True
        return result

    # ── Internal ──────────────────────────────────────

    @staticmethod
    def _cast(value: str, value_type: str) -> Any:
        """Cast a string value to the declared type."""
        try:
            if value_type == "float":
                return float(value)
            elif value_type == "int":
                return int(float(value))
            elif value_type == "bool":
                return value.lower() in ("true", "1", "yes")
            else:
                return value
        except (TypeError, ValueError):
            return value
