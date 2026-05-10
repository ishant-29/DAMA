from pydantic_settings import BaseSettings
from pydantic import validator, Field
from typing import List, Optional
import os


def _read_version() -> str:
    """Read version from VERSION file at project root."""
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "..", "VERSION"),  # backend/../../
        os.path.join(os.path.dirname(__file__), "..", "VERSION"),         # backend/../
        os.path.join(os.path.dirname(__file__), "VERSION"),               # backend/
        os.path.join(os.getcwd(), "VERSION"),                             # current working dir
    ]
    for path in candidates:
        if os.path.isfile(path):
            with open(path) as f:
                return f.read().strip()
    return "2.0.0"


class Settings(BaseSettings):
    # ── Application ──────────────────────────────────────
    PROJECT_NAME: str = "NSE Signal Engine"
    VERSION: str = _read_version()
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False

    # ── Database ─────────────────────────────────────────
    DATABASE_URL: str = Field(default="postgresql://user:password@localhost:5432/nse_db")
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE: int = 3600  # 1 hour

    # ── Redis ────────────────────────────────────────────
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    REDIS_TTL: int = 3600  # 1 hour cache
    REDIS_DEFAULT_TTL: int = 90  # default TTL for API response cache

    # ── Security ─────────────────────────────────────────
    ALLOWED_ORIGINS: str = "http://localhost:5174,http://localhost:5173,http://127.0.0.1:5174,http://127.0.0.1:5173"
    SECRET_KEY: str = Field(...)  # required env var
    ALLOW_REGISTRATION: bool = True

    # ── Auth / JWT ───────────────────────────────────────
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 4  # Reduced from 24h for security
    JWT_REFRESH_HOURS: int = 24  # Refresh token valid for 24h
    MIN_PASSWORD_LENGTH: int = 8

    # ── Cache TTL Constants (seconds) ────────────────────
    CACHE_TTL_SHORT: int = 1800    # 30 minutes
    CACHE_TTL_MEDIUM: int = 5400   # 90 minutes
    CACHE_TTL_LONG: int = 86400    # 24 hours
    SECTOR_CACHE_TTL: int = 3600   # 60 minutes for sector scores
    SIGNAL_HIGH_CONFIDENCE: float = 0.75

    # ── ML Models ────────────────────────────────────────
    ML_ARTIFACTS_PATH: str = "app/artifacts"
    ML_CONFIDENCE_THRESHOLD: float = 0.60
    SELL_CONFIDENCE_THRESHOLD: float = 0.50

    # ── Trading Parameters ───────────────────────────────
    VOLUME_MULTIPLIER: float = 1.2
    SECTOR_THRESHOLD: float = 0.0
    LOOKAHEAD_DAYS: int = 7
    ROLLING_WINDOW: int = 100
    VOLUME_ROLLING_WINDOW: int = 20

    # ── Signal Engine ────────────────────────────────────
    SIGNAL_BASE_CONFIDENCE: float = 0.70
    SIGNAL_BATCH_SIZE: int = 10
    TELEGRAM_ALERT_CONFIDENCE: float = 0.82
    
    # ── Signal Confidence Calculation ─────────────────────
    # Base scores
    SIGNAL_BASE_SCORE: float = 0.70
    # EMA divergence bonus (capped)
    SIGNAL_EMA_DIVERGENCE_BONUS_MAX: float = 0.15
    # Volume confirmation bonuses
    SIGNAL_VOLUME_BONUS_1_5X: float = 0.05   # >1.5x avg volume
    SIGNAL_VOLUME_BONUS_2_0X: float = 0.03   # >2.0x avg volume
    # Momentum bonus (per consecutive candle)
    SIGNAL_MOMENTUM_BONUS_PER_CANDLE: float = 0.02
    # Sector momentum bonus (capped)
    SIGNAL_SECTOR_MOMENTUM_BONUS_MAX: float = 0.10
    # Confidence cap
    SIGNAL_CONFIDENCE_MAX: float = 0.99
    SIGNAL_CONFIDENCE_MIN: float = 0.01
    # High risk volume threshold multiplier
    SIGNAL_HIGH_RISK_VOLUME_MIN: float = 1.2
    # Fundamental grade bonus
    SIGNAL_FUNDAMENTAL_BONUS: float = 0.03

    # ── External APIs ────────────────────────────────────
    YFINANCE_RATE_LIMIT: int = 2000  # requests per hour

    # ── Notifications ────────────────────────────────────
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None

    # ── Data Paths ───────────────────────────────────────
    DATA_DIR: str = "app/data"
    SAMPLE_DATA_PATH: str = "./sample_data"
    DATA_FETCH_WORKERS: int = 10

    # ── Logging ──────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"
    LOG_MAX_BYTES: int = 10485760  # 10 MB
    LOG_BACKUP_COUNT: int = 5

    # ── Date Windows & Thresholds ────────────────────────
    RECENT_SELL_WINDOW_DAYS: int = 3
    HIGH_RISK_WINDOW_DAYS: int = 5
    SIGNAL_MAX_AGE_DAYS: int = 7
    MARKET_MOOD_WINDOW_DAYS: int = 5

    # ── Scheduler (UTC times) ────────────────────────────
    SCHEDULER_TIME_UTC_HOUR: int = 11
    SCHEDULER_TIME_UTC_MINUTE: int = 30
    GRADE_OUTCOMES_HOUR: int = 22
    GRADE_OUTCOMES_MINUTE: int = 0
    PAPER_OPEN_HOUR: int = 3
    PAPER_OPEN_MINUTE: int = 50
    PAPER_MONITOR_HOUR: int = 10
    PAPER_MONITOR_MINUTE: int = 15
    WATCHDOG_INTERVAL_HOURS: int = 2
    WATCHDOG_STALE_HOURS: int = 25
    STARTUP_UPDATE_THRESHOLD_HOURS: int = 24

    # ── Cache & Performance ──────────────────────────────
    PRICE_CACHE_EXPIRY_MINUTES: int = 10

    # ── Backtest Defaults ────────────────────────────────
    BACKTEST_DEFAULT_INITIAL_CAPITAL: float = 100000.0
    BACKTEST_DEFAULT_POSITION_SIZE: float = 0.10
    BACKTEST_DATA_PERIOD: str = "2y"
    BACKTEST_HOLD_DAYS: int = 15
    BACKTEST_ATR_STOP_MULT: float = 1.5
    BACKTEST_ATR_TARGET_MULT: float = 3.0
    BACKTEST_LOOKBACK: int = 60
    BACKTEST_EMA_PERIODS: str = "10,20,50"  # comma-separated
    BACKTEST_VOLUME_THRESHOLD: float = 1.8
    BACKTEST_RR_THRESHOLD: float = 1.5
    BACKTEST_DEFAULT_STOP_LOSS: float = 0.05
    BACKTEST_DEFAULT_TAKE_PROFIT: float = 0.10

    # ── Trade Logic ──────────────────────────────────────
    TRADE_EXPIRY_DAYS: int = 90
    STOP_LOSS_MULTIPLIER: float = 0.88     # 12% risk
    TRAILING_STOP_ACTIVATION: float = 1.025  # activate after +2.5% gain
    TRAILING_STOP_DISTANCE: float = 0.01     # trail by 1.0%
    HOLD_STATUS_THRESHOLD_PERCENT: float = 1.5

    # ── Paper Trading ────────────────────────────────────
    PAPER_MAX_POSITIONS: int = 5
    PAPER_MAX_DRAWDOWN_HALT: float = 8.0
    PAPER_DEFAULT_CAPITAL: float = 1_000_000.0
    PAPER_STOP_LOSS_DEFAULT: float = 0.93   # multiplier on entry price
    PAPER_TARGET_DEFAULT: float = 1.09      # multiplier on entry price
    PAPER_MIN_ALLOCATION: float = 5000.0
    PAPER_DEFAULT_RR: float = 1.5

    # ── Position Sizing ──────────────────────────────────
    POSITION_MAX_PCT: float = 0.15
    POSITION_MAX_SECTOR_PCT: float = 0.25
    POSITION_TIER_FULL: float = 0.12
    POSITION_TIER_HALF: float = 0.07
    POSITION_TIER_QUARTER: float = 0.03
    POSITION_DRAWDOWN_HALT: float = 8.0

    # ── Tax Rates (India) ────────────────────────────────
    STCG_RATE: float = 0.15
    LTCG_RATE: float = 0.10
    LTCG_EXEMPTION: float = 100_000.0
    SHORT_TERM_DAYS: int = 365

    # ── Validators ───────────────────────────────────────

    @validator('DATABASE_URL')
    def validate_database_url(cls, v):
        if not v.startswith('postgresql://'):
            raise ValueError('DATABASE_URL must be a PostgreSQL connection string')
        return v

    @validator('ALLOWED_ORIGINS')
    def validate_origins(cls, v):
        if v == "*":
            raise ValueError('ALLOWED_ORIGINS cannot be "*" in production. Specify exact origins.')
        return v

    @validator('SECRET_KEY')
    def validate_secret_key(cls, v):
        if not v:
            raise ValueError('SECRET_KEY is required')
        if len(v) < 32:
            raise ValueError('SECRET_KEY must be at least 32 characters. Generate: openssl rand -hex 32')
        if len(v) < 64:
            import warnings
            warnings.warn('SECRET_KEY should be at least 64 characters for production (256-bit). Generate: openssl rand -hex 32')
        return v

    @property
    def allowed_origins_list(self) -> List[str]:
        """Parse comma-separated ALLOWED_ORIGINS into a list."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def backtest_ema_periods_list(self) -> List[int]:
        """Parse comma-separated BACKTEST_EMA_PERIODS into a list of ints."""
        return [int(p.strip()) for p in self.BACKTEST_EMA_PERIODS.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

settings = Settings()
