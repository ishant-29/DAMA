import os
import logging

class TelegramService:
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.enabled = bool(self.bot_token and self.chat_id)
        
    def send_message(self, message: str):
        if not self.enabled:
            logging.info("Telegram not configured, skipping: %s", message)
            return
            
        # Stub implementation
        # requests.post(f"https://api.telegram.org/bot{self.bot_token}/sendMessage", ...)
        logging.info("Sending Telegram message: %s", message)

    def notify_signal(self, signal):
        msg = f"SIGNAL: {signal.signal_type} {signal.symbol}\nConf: {signal.confidence:.2f}"
        self.send_message(msg)
