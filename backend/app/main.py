from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import uuid

from app.api import routes_signals, routes_fetch, routes_model, routes_sector  # FIXED: S1-03 — removed routes_health
from app.api import routes_backtest, routes_analytics, routes_performance
from app.api.routes_paper import router as paper_router
from app.api.routes_admin import router as admin_router
from app.api.routes_user import router as user_router
from app.auth import router as auth_router, User, get_current_user_from_token  # FIXED: S3-05 — import token validator
from app.api.websocket import manager as ws_manager
from app.db.session import engine, SessionLocal
from app.db.models import Base, Signal
from app.core import scheduler
from app.core.config import settings
from app.core.logging import logger
from datetime import datetime, timezone
import time
from sqlalchemy import text

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# CORS Configuration - Add BEFORE app creation for preflight handling
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174", 
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "ws://localhost:8000",
    "ws://127.0.0.1:8000",
]

def get_cors_origins():
    """Get CORS origins from settings or fall back to defaults."""
    try:
        if settings.ALLOWED_ORIGINS and settings.ALLOWED_ORIGINS != "*":
            return settings.allowed_origins_list
    except:
        pass
    return CORS_ORIGINS

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Create database tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")
    
    # Startup
    logger.info("Starting NSE Signal Engine...")
    scheduler.start_scheduler()
    logger.info("Scheduler started successfully")
    yield
    # Shutdown
    logger.info("Shutting down NSE Signal Engine...")
    # FIXED: S9-06 — graceful WebSocket shutdown
    for ws in list(ws_manager.active_connections):
        try:
            await ws.close(code=1001)  # 1001 = going away
        except Exception:
            pass
    scheduler.shutdown_scheduler()

app = FastAPI(
    title="NSE Signal Engine API",
    description="""
    ## Overview
    Production-ready trading signals for NSE 500 stocks using ML-validated technical analysis.
    
    ## Features
    - **Real-time Signals**: Buy/Sell signals based on strict trading rules
    - **ML Validation**: XGBoost/RandomForest confidence scoring
    - **Sector Analysis**: Momentum-based sector scoring
    
    ## Rate Limits
    - Most endpoints: 60 requests/minute
    - Signal endpoints: 30 requests/minute
    """,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS Configuration - MUST be added first (outermost middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    expose_headers=["X-Request-ID"],
)

# Add rate limiter state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Log headers middleware
@app.middleware("http")
async def log_headers(request: Request, call_next):
    origin = request.headers.get("origin")
    if origin:
        logger.info(f"Incoming Request Origin: {origin} | Path: {request.url.path}")
    response = await call_next(request)
    return response

# Include routers

# Include routers — FIXED: S1-03 — removed routes_health router
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(routes_signals.router, prefix="/signals", tags=["signals"])
app.include_router(routes_fetch.router, prefix="/fetch", tags=["fetch"])
app.include_router(routes_model.router, prefix="/model", tags=["model"])
app.include_router(routes_sector.router, prefix="/sector", tags=["sector"])
app.include_router(routes_backtest.router, prefix="/backtest", tags=["backtesting"])
app.include_router(routes_analytics.router, prefix="/analytics", tags=["analytics"])
app.include_router(routes_performance.router, prefix="/performance", tags=["performance"])
app.include_router(paper_router)
app.include_router(admin_router)
app.include_router(user_router)

# FIXED: S3-05 — WebSocket endpoint with token authentication
@app.websocket("/ws/signals")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time signal updates."""
    try:
        token = websocket.query_params.get("token")
        logger.info(f"Incoming WebSocket connection attempt with token snippet: {str(token)[:10]}...")
        
        # WebSocket token authentication
        if not token:
            logger.warning("WebSocket auth failed: No token provided")
            await websocket.close(code=1008)
            return
        
        from app.db.session import SessionLocal
        db = SessionLocal()
        user = get_current_user_from_token(token, db)
        db.close()
        if user is None:
            logger.warning(f"WebSocket auth failed: Invalid or expired token for token snippet {token[:20]}...")
            await websocket.close(code=1008)  # 1008 = policy violation
            return
        logger.info(f"WebSocket auth success for user: {user.username}")

        client_id = str(uuid.uuid4())
        await ws_manager.connect(websocket, client_id)
        
        try:
            while True:
                data = await websocket.receive_text()
                # Handle ping/pong for heartbeat
                if data.strip() == "ping":
                    await ws_manager.send_personal_message(
                        {"type": "pong", "timestamp": time.time()},
                        websocket
                    )
                else:
                    await ws_manager.send_personal_message(
                        {"type": "pong", "message": "connected"},
                        websocket
                    )
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)
            logger.info(f"Client {client_id} disconnected")
        except Exception as e:
            logger.error(f"WebSocket error for client {client_id}: {e}")
            ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass

logger.info("NSE Signal Engine initialized successfully")


# FIXED: S1-03 — single comprehensive health endpoint (no auth — public)
@app.get("/health")
async def health_check():
    """Uptime monitoring endpoint — public, no auth required."""
    health = {
        'status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat(),  # FIXED: S5-01
        'version': settings.VERSION,
    }
    db = None
    try:
        db = SessionLocal()
        last_signal = db.query(Signal).order_by(Signal.created_at.desc()).first()
        if last_signal:
            hours = (datetime.now(timezone.utc) - last_signal.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600  # FIXED: S5-01
            health['last_signal_hours_ago'] = round(hours, 1)
            health['scheduler_ok'] = hours < 26
        else:
            health['scheduler_ok'] = False
    except Exception as e:
        health['status'] = 'degraded'
        health['db_error'] = str(e)
    finally:
        if db:
            db.close()
    return health


@app.get("/health/deep")
async def deep_health_check():
    """
    Deep health check - verifies all external dependencies.
    Returns detailed status of DB, Redis, and external services.
    """
    health = {
        'status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'version': settings.VERSION,
        'components': {},
    }
    
    # Check PostgreSQL
    db = None
    try:
        db = SessionLocal()
        result = db.execute(text("SELECT 1"))
        result.scalar()  # Execute to verify connection works
        health['components']['postgresql'] = {'status': 'ok', 'details': 'Connected'}
        
        # Check for recent signals
        last_signal = db.query(Signal).order_by(Signal.created_at.desc()).first()
        if last_signal:
            hours = (datetime.now(timezone.utc) - last_signal.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600
            health['components']['postgresql']['last_signal_hours'] = round(hours, 1)
    except Exception as e:
        health['components']['postgresql'] = {'status': 'error', 'error': str(e)}
        health['status'] = 'degraded'
    finally:
        if db:
            db.close()
    
    # Check Redis
    try:
        import redis.asyncio as aioredis
        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pong = await redis_client.ping()
        health['components']['redis'] = {'status': 'ok', 'details': 'Connected' if pong else 'Failed'}
        await redis_client.aclose()
    except Exception as e:
        health['components']['redis'] = {'status': 'error', 'error': str(e)}
        health['status'] = 'degraded'
    
    # Check Circuit Breakers
    try:
        from app.services.circuit_breaker import get_all_circuit_breakers_status
        health['components']['circuit_breakers'] = get_all_circuit_breakers_status()
    except Exception as e:
        health['components']['circuit_breakers'] = {'status': 'error', 'error': str(e)}
    
    # Check yfinance (sample ticker)
    try:
        import yfinance as yf
        ticker = yf.Ticker("RELIANCE.NS")
        info = ticker.info
        if info and 'regularMarketPrice' in info:
            health['components']['yfinance'] = {'status': 'ok', 'details': 'API responding'}
        else:
            health['components']['yfinance'] = {'status': 'degraded', 'details': 'Limited data'}
    except Exception as e:
        health['components']['yfinance'] = {'status': 'error', 'error': str(e)}
        health['status'] = 'degraded'
    
    # Overall status
    component_errors = [
        c for c, v in health.get('components', {}).items() 
        if isinstance(v, dict) and v.get('status') == 'error'
    ]
    if component_errors:
        health['status'] = 'unhealthy'
        health['failed_components'] = component_errors
    
    return health

# CORS middleware is added at the top of the file (after app creation) for proper preflight handling
