"""Paper Trading API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional
import io

from app.db.session import get_db
from app.services.paper_trader import PaperTradingEngine
from app.services.tax_reporter import TaxReporter
from app.auth import get_current_user, User  # FIXED: S3-04 — add auth import
from app.core.config import settings

router = APIRouter(prefix="/paper", tags=["Paper Trading"])
engine = PaperTradingEngine()
tax_reporter = TaxReporter()


@router.post("/portfolio")
def create_portfolio(
    name: str = "Paper Portfolio",
    capital: float = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # FIXED: S3-04
):
    """Create a new paper trading portfolio."""
    portfolio = engine.create_portfolio(db, name=name, capital=capital or settings.PAPER_DEFAULT_CAPITAL)
    return {
        "id": portfolio.id,
        "name": portfolio.name,
        "initial_capital": portfolio.initial_capital,
    }


@router.get("/portfolio")
def get_portfolio(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):  # FIXED: S3-04
    """Get active portfolio performance report."""
    return engine.get_performance_report(db)


@router.post("/monitor")
def trigger_monitoring(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):  # FIXED: S3-04
    """Manually trigger position monitoring."""
    return engine.monitor_open_positions(db)

@router.post("/trade/{symbol}")
def execute_paper_trade(
    symbol: str, 
    quantity: int = Query(..., ge=1, description="Must be >= 1"),  # FIXED: S6-02 — validate quantity
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # FIXED: S3-04
):
    """Execute a paper trade based on the latest signal for a symbol."""
    from app.db.models import Signal
    
    # Find the latest signal
    latest_signal = db.query(Signal).filter(Signal.symbol == symbol).order_by(Signal.timestamp.desc()).first()
    
    if not latest_signal:
        raise HTTPException(status_code=404, detail=f"No saved signal found for {symbol}.")
        
    if latest_signal.signal_type != "BUY":
        raise HTTPException(status_code=400, detail="Only BUY signals can be executed as paper trades.")
        
    # Execute trade using the engine
    trade = engine.open_trade_from_signal(latest_signal, db, custom_quantity=quantity)
    if not trade:
        raise HTTPException(status_code=400, detail="Failed to execute trade. Check portfolio cash balance, max positions, or drawdown limits.")
        
    return {
        "id": trade.id,
        "symbol": trade.symbol,
        "entry_price": trade.entry_price,
        "quantity": trade.quantity,
        "allocated_capital": trade.allocated_capital
    }


@router.post("/trade/{trade_id}/close")
def close_paper_trade(
    trade_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually close an open paper trade."""
    trade = engine.manually_close_trade(db, trade_id)
    if not trade:
        raise HTTPException(status_code=400, detail="Failed to close trade. It might already be closed or not found.")
        
    return {
        "id": trade.id,
        "symbol": trade.symbol,
        "exit_price": trade.exit_price,
        "pnl_amount": trade.pnl_amount,
        "pnl_pct": trade.pnl_pct,
        "status": trade.status.value
    }


@router.get("/trades")
def get_all_trades(status: str = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):  # FIXED: S3-04
    """Get all paper trades, optionally filtered by status."""
    from app.db.models import PaperTrade

    portfolio = engine.get_active_portfolio(db)
    if not portfolio:
        raise HTTPException(status_code=404, detail="No active portfolio")

    query = db.query(PaperTrade).filter(PaperTrade.portfolio_id == portfolio.id)
    if status:
        query = query.filter(PaperTrade.status == status.upper())

    trades = query.order_by(PaperTrade.entry_date.desc()).limit(100).all()
    return [
        {
            "id": t.id, "symbol": t.symbol, "status": t.status.value if t.status else None,
            "entry_price": t.entry_price, "exit_price": t.exit_price,
            "pnl_pct": t.pnl_pct, "pnl_amount": t.pnl_amount,
            "holding_days": t.holding_days, "exit_reason": t.exit_reason,
        }
        for t in trades
    ]


# ── Tax Report Endpoints ──────────────────────────

@router.get("/tax-report")
def get_tax_report(financial_year: str = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):  # FIXED: S3-04
    """Get annual tax report for paper trades."""
    return tax_reporter.generate_annual_report(db, financial_year)


@router.get("/tax-report/csv")
def download_tax_csv(financial_year: str = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):  # FIXED: S3-04
    """Download tax report as CSV."""
    report = tax_reporter.generate_annual_report(db, financial_year)
    csv_content = tax_reporter.export_to_csv(report)
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=tax_report_{report['financial_year']}.csv"
        },
    )
