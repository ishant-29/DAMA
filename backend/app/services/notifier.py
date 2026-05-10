"""
Telegram notification service for high-confidence trading signals.
Sends alerts to a configured Telegram chat when high-confidence BUY signals
are generated.
"""
import logging
from typing import Dict, Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_signal_alert(signal_data: Dict[str, Any]) -> None:
    """
    Send a Telegram message for a high-confidence BUY signal.
    Only fires if:
    - TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are configured
    - signal_type == 'BUY'
    - confidence >= 0.82
    """
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
    chat_id = getattr(settings, "TELEGRAM_CHAT_ID", None)

    if not token or not chat_id:
        return  # Telegram not configured — silently skip

    if signal_data.get("signal_type") != "BUY":
        return

    confidence = signal_data.get("confidence", 0)
    if confidence < 0.82:
        return

    symbol = signal_data.get("symbol", "UNKNOWN")
    sector = signal_data.get("sector", "—")
    reason = signal_data.get("reason", {})

    text = (
        f"🚀 *HIGH-CONFIDENCE BUY SIGNAL*\n\n"
        f"*Symbol:* `{symbol}`\n"
        f"*Confidence:* `{confidence*100:.0f}%`\n"
        f"*Sector:* {sector}\n"
        f"*EMA Pass:* {'✅' if reason.get('ema_condition') else '❌'}\n"
        f"*Darvas Break:* {'✅' if reason.get('darvas_condition') else '❌'}\n"
    )

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                logger.info(f"Telegram alert sent for {symbol}")
            else:
                logger.warning(f"Telegram API returned {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.error(f"Telegram alert failed for {symbol}: {e}")
