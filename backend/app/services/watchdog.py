"""
Watchdog — sends Telegram alert if scheduler hasn't run in configurable hours.
Prevents silent failures where signals stop generating with no warning.
"""

import httpx
import os
from datetime import datetime, date
from sqlalchemy.orm import Session
from app.db.models import Signal
from app.core.config import settings
from app.services.market_calendar import MarketCalendarService
import logging

logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


async def send_telegram(message: str):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": CHAT_ID, "text": message},
            )
    except Exception as e:
        logger.error(f"Telegram alert failed: {e}")


async def check_scheduler_health(db: Session):
    """Run periodically. Alerts if no signals in configured hours on a trading day."""
    today = date.today()
    if not MarketCalendarService.is_trading_day(today, db):
        return

    last_signal = db.query(Signal).order_by(Signal.created_at.desc()).first()

    if not last_signal:
        await send_telegram("⚠️ NSE Signal Engine: No signals in database at all!")
        return

    hours_since = (datetime.utcnow() - last_signal.created_at).total_seconds() / 3600

    if hours_since > settings.WATCHDOG_STALE_HOURS:
        await send_telegram(
            f"🚨 NSE SIGNAL ENGINE ALERT\n"
            f"No signals generated in {hours_since:.0f} hours!\n"
            f"Last signal: {last_signal.created_at.strftime('%Y-%m-%d %H:%M')} UTC\n"
            f"Check: scheduler may have crashed.\n"
            f"Action: docker-compose logs backend"
        )
    else:
        logger.debug(f"Watchdog OK — last signal {hours_since:.1f}h ago")
