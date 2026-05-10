from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, JSON, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, timezone  # FIXED: S5-01 — use timezone-aware
import enum

Base = declarative_base()

class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String, unique=True, index=True)
    symbol = Column(String, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))  # FIXED: S5-01
    recommendation_date = Column(DateTime) # Explicit trading date
    
    signal_type = Column(String) # BUY / SELL
    reason = Column(JSON) # {ema_verified: true, darvas_verified: true, ...}
    
    confidence = Column(Float)
    sector_score = Column(Float)
    model_version = Column(String)
    
    processed = Column(Boolean, default=False)

    # --- Outcome tracking (Phase 6: feedback loop) ---
    outcome_pnl_pct = Column(Float, nullable=True)
    outcome_grade = Column(String(1), nullable=True)   # A/B/C/D/F
    outcome_exit_price = Column(Float, nullable=True)
    outcome_graded_at = Column(DateTime, nullable=True)

    # --- Advanced feature snapshots (Phase 1) ---
    volume_ratio = Column(Float, nullable=True)
    atr_ratio = Column(Float, nullable=True)
    market_regime = Column(String(30), nullable=True)
    reward_risk_ratio = Column(Float, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))  # FIXED: S5-01
    
    # Relations  # FIXED: S5-02 — add cascade delete
    outcome = relationship("SignalOutcome", back_populates="signal", uselist=False, cascade="all, delete-orphan")
    trades = relationship("Trade", back_populates="entry_signal", cascade="all, delete-orphan")  # FIXED: S5-02

class ModelRun(Base):
    __tablename__ = "model_runs"
    
    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String)
    version = Column(String)
    algorithm = Column(String, default="xgboost")  # xgboost, random_forest, lightgbm
    training_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))  # FIXED: S5-01
    accuracy = Column(Float, nullable=True)
    f1_score = Column(Float, nullable=True)
    file_path = Column(String, nullable=True)
    is_active = Column(Boolean, default=False)
    metrics = Column(JSON)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))  # FIXED: S5-01


class SectorMapping(Base):
    """Stores NSE 500 symbol-to-sector mappings (migrated from CSV)."""
    __tablename__ = "sector_mappings"

    symbol = Column(String, primary_key=True, index=True)
    sector = Column(String, nullable=False)
    industry = Column(String, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))  # FIXED: S5-01

class OutcomeType(str, enum.Enum):
    WIN = "WIN"
    LOSS = "LOSS"
    NEUTRAL = "NEUTRAL"

class SignalOutcome(Base):
    __tablename__ = "signal_outcomes"
    
    id = Column(Integer, primary_key=True, index=True)
    signal_id = Column(Integer, ForeignKey('signals.id'))
    
    outcome = Column(String) # WIN, LOSS, NEUTRAL
    pnl_percent = Column(Float)
    closed_at = Column(DateTime)
    
    signal = relationship("Signal", back_populates="outcome")

class AutoTuneEvent(Base):
    __tablename__ = "auto_tune_events"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))  # FIXED: S5-01
    
    trigger_reason = Column(String)
    
    old_confidence_threshold = Column(Float)
    new_confidence_threshold = Column(Float)
    
    old_volume_multiplier = Column(Float)
    new_volume_multiplier = Column(Float)

class Trade(Base):
    """
    Represents a full trade cycle from BUY to SELL (or EXPIRY).
    Tracks the lifecycle across multiple days.
    """
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    
    # Entry Info
    signal_id = Column(Integer, ForeignKey('signals.id')) 
    entry_date = Column(DateTime, index=True) # Date of the BUY signal
    entry_price = Column(Float)
    
    # Exit Info
    exit_date = Column(DateTime, nullable=True) # Date of SELL or Expiry
    exit_price = Column(Float, nullable=True)
    
    # Status
    status = Column(String, default="OPEN", index=True) # OPEN, CLOSED, EXPIRED
    exit_reason = Column(String, nullable=True) # SIGNAL_SELL, TIME_EXPIRY, FORCE_CLOSE
    
    # Performance
    pnl_percent = Column(Float, nullable=True)
    holding_days = Column(Integer, nullable=True)
    
    # Relationships
    entry_signal = relationship("Signal", back_populates="trades")  # FIXED: S5-02 — match parent cascade

class DailyPerformance(Base):
    """
    Stores rolling 90-day performance metrics for each day.
    Calculated at the end of every update cycle.
    """
    __tablename__ = "daily_performance"

    date = Column(DateTime, primary_key=True) # The date for which stats are calculated
    
    # Rolling 90-Day Metrics
    # Rolling Metrics (7D, 30D, 90D)
    total_trades_active = Column(Integer)
    
    # 7 Days
    total_signals_7d = Column(Integer, default=0)
    win_rate_7d = Column(Float, default=0.0)
    avg_return_7d = Column(Float, default=0.0)
    
    # 30 Days
    total_signals_30d = Column(Integer, default=0)
    win_rate_30d = Column(Float, default=0.0)
    avg_return_30d = Column(Float, default=0.0)

    # 90 Days
    total_signals_90d = Column(Integer, default=0)
    win_rate_90d = Column(Float, default=0.0)
    avg_return_90d = Column(Float, default=0.0)
    max_drawdown_90d = Column(Float, default=0.0)
    
    # Optional: Sector breakdown JSON
    sector_performance = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))  # FIXED: S5-01


# ═════════════════════════════════════════
# PAPER TRADING MODELS
# ═════════════════════════════════════════

class TradeStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED_TARGET = "CLOSED_TARGET"
    CLOSED_STOP = "CLOSED_STOP"
    CLOSED_MANUAL = "CLOSED_MANUAL"
    CLOSED_TIME = "CLOSED_TIME"


class PaperPortfolio(Base):
    __tablename__ = "paper_portfolios"

    id = Column(Integer, primary_key=True)
    name = Column(String, default="Paper Portfolio")
    initial_capital = Column(Float, default=1_000_000.0)
    current_cash = Column(Float, default=1_000_000.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))  # FIXED: S5-01
    is_active = Column(Boolean, default=True)

    trades = relationship("PaperTrade", back_populates="portfolio", cascade="all, delete-orphan")  # FIXED: S5-02

    @property
    def total_invested(self):
        open_trades = [t for t in self.trades if t.status == TradeStatus.OPEN]
        return sum(t.entry_price * t.quantity for t in open_trades)

    @property
    def total_value(self):
        return self.current_cash + self.total_invested

    @property
    def total_pnl(self):
        return self.total_value - self.initial_capital

    @property
    def total_pnl_pct(self):
        if self.initial_capital == 0:
            return 0.0
        return (self.total_pnl / self.initial_capital) * 100


class PaperTrade(Base):
    __tablename__ = "paper_trades"

    id = Column(Integer, primary_key=True)
    portfolio_id = Column(Integer, ForeignKey("paper_portfolios.id"))
    signal_id = Column(Integer, ForeignKey("signals.id"), nullable=True)

    symbol = Column(String, nullable=False)
    sector = Column(String, nullable=True)

    # Entry
    entry_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))  # FIXED: S5-01
    entry_price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False)
    allocated_capital = Column(Float)
    allocation_pct = Column(Float)

    # Exit targets
    stop_loss = Column(Float)
    target_price = Column(Float)
    reward_risk_ratio = Column(Float)
    max_hold_days = Column(Integer, default=15)

    # Signal metadata
    signal_confidence = Column(Float)
    kelly_allocation_pct = Column(Float)
    market_regime = Column(String, nullable=True)
    sector_momentum_score = Column(Float, nullable=True)

    # Exit
    status = Column(SAEnum(TradeStatus), default=TradeStatus.OPEN)
    exit_date = Column(DateTime, nullable=True)
    exit_price = Column(Float, nullable=True)
    pnl_amount = Column(Float, nullable=True)
    pnl_pct = Column(Float, nullable=True)
    exit_reason = Column(String, nullable=True)

    # Tax
    holding_days = Column(Integer, nullable=True)
    tax_category = Column(String, nullable=True)  # STCG / LTCG

    portfolio = relationship("PaperPortfolio", back_populates="trades")


class PaperPerformanceSnapshot(Base):
    __tablename__ = "paper_performance_snapshots"

    id = Column(Integer, primary_key=True)
    portfolio_id = Column(Integer, ForeignKey("paper_portfolios.id"))
    snapshot_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))  # FIXED: S5-01
    total_value = Column(Float)
    cash = Column(Float)
    invested = Column(Float)
    daily_pnl = Column(Float)
    cumulative_pnl_pct = Column(Float)
    open_positions = Column(Integer)
    drawdown_pct = Column(Float)


# ═════════════════════════════════════════
# RUNTIME CONFIGURATION
# ═════════════════════════════════════════

class SystemConfig(Base):
    """Key-value store for runtime-configurable system settings."""
    __tablename__ = "system_config"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
    value_type = Column(String, nullable=False, default="str")  # float, int, str, bool
    description = Column(String, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
    updated_by = Column(String, nullable=True)


class UserSettings(Base):
    """Per-user trading parameter overrides."""
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    stop_loss_pct = Column(Float, default=0.05)
    take_profit_pct = Column(Float, default=0.10)
    position_size_pct = Column(Float, default=0.10)
    initial_capital = Column(Float, default=1_000_000.0)
    min_confidence = Column(Float, default=0.60)
    max_positions = Column(Integer, default=5)
    kelly_fraction = Column(Float, default=0.50)
    commission_rate = Column(Float, default=0.001)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class MarketHoliday(Base):
    """NSE market holidays — used by MarketCalendarService."""
    __tablename__ = "market_holidays"

    id = Column(Integer, primary_key=True)
    date = Column(String, unique=True, index=True, nullable=False)  # YYYY-MM-DD
    description = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_by = Column(String, nullable=True)


class StockUniverse(Base):
    """DB-backed stock universe — replaces CSV-only symbol lists."""
    __tablename__ = "stock_universe"

    id = Column(Integer, primary_key=True)
    symbol = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    sector = Column(String, index=True, nullable=True)
    industry = Column(String, nullable=True)
    index_name = Column(String, index=True, default="NIFTY500")
    is_active = Column(Boolean, default=True, index=True)
    added_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
