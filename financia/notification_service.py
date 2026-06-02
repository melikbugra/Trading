"""
Telegram notification service (one-way push).

Replaces the old SMTP/email notifications. Sends messages to a single chat via
the Telegram Bot API. Configure BOT_TOKEN and CHAT_ID in financia/telegram_config.py
(git-ignored) or via env vars TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID.
"""

import os
import threading

import requests

# Configuration
try:
    from financia.telegram_config import TELEGRAM_CONFIG

    BOT_TOKEN = TELEGRAM_CONFIG.get("BOT_TOKEN", "")
    CHAT_ID = str(TELEGRAM_CONFIG.get("CHAT_ID", ""))
except ImportError:
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    CHAT_ID = str(os.getenv("TELEGRAM_CHAT_ID", ""))


# Import simulation time manager to check if in simulation mode
try:
    from financia.web_api.database import simulation_time_manager
except ImportError:
    simulation_time_manager = None


# Telegram hard limit per message
_MAX_LEN = 4096


class TelegramService:
    @staticmethod
    def is_configured() -> bool:
        return bool(BOT_TOKEN) and bool(CHAT_ID)

    @staticmethod
    def _send_sync(text: str):
        """
        Send a message synchronously via the Telegram Bot API. Bypasses the
        simulation-mode guard (used directly for backtest summaries). Long
        messages are split into <=_MAX_LEN chunks. No-op if not configured.
        """
        if not TelegramService.is_configured():
            print("[TelegramService] Skipping: BOT_TOKEN/CHAT_ID not set.")
            return

        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        try:
            for chunk in TelegramService._chunks(text):
                resp = requests.post(
                    url,
                    data={
                        "chat_id": CHAT_ID,
                        "text": chunk,
                        "disable_web_page_preview": True,
                    },
                    timeout=10,
                )
                if resp.status_code != 200:
                    print(
                        f"[TelegramService] Send failed ({resp.status_code}): {resp.text[:200]}"
                    )
                    break
            else:
                print("[TelegramService] Message sent.")
        except Exception as e:
            print(f"[TelegramService] Failed to send message: {e}")

    @staticmethod
    def _chunks(text: str):
        """Split text into Telegram-sized chunks, preferring line boundaries."""
        if len(text) <= _MAX_LEN:
            yield text
            return
        buf = ""
        for line in text.split("\n"):
            # A single very long line still has to be hard-split
            while len(line) > _MAX_LEN:
                if buf:
                    yield buf
                    buf = ""
                yield line[:_MAX_LEN]
                line = line[_MAX_LEN:]
            if len(buf) + len(line) + 1 > _MAX_LEN:
                yield buf
                buf = line
            else:
                buf = f"{buf}\n{line}" if buf else line
        if buf:
            yield buf

    @staticmethod
    def send(text: str):
        """
        High-level send used for live notifications. Skipped while a (live-step)
        simulation is active to avoid spam, mirroring the previous email behavior.
        Runs in a background thread so it never blocks the app.
        """
        if simulation_time_manager and simulation_time_manager.is_active:
            print("[TelegramService] Skipping: Simulation mode active.")
            return
        if not TelegramService.is_configured():
            print("[TelegramService] Skipping: BOT_TOKEN/CHAT_ID not set.")
            return
        threading.Thread(target=TelegramService._send_sync, args=(text,)).start()

    @staticmethod
    def send_message(subject: str, body: str):
        """Generic notification (e.g. EOD analysis). Combines subject + body."""
        TelegramService.send(f"{subject}\n\n{body}".strip())

    @staticmethod
    def send_signal_triggered(
        ticker,
        market,
        direction,
        entry_price,
        stop_loss,
        take_profit,
        current_price,
        strategy_name="",
    ):
        """Notify when a new signal is triggered."""
        emoji = "🟢" if direction == "long" else "🔴"
        direction_tr = "LONG (Al)" if direction == "long" else "SHORT (Sat)"

        if direction == "long":
            risk = entry_price - stop_loss
            reward = take_profit - entry_price
        else:
            risk = stop_loss - entry_price
            reward = entry_price - take_profit
        rr = reward / risk if risk > 0 else 0

        text = (
            f"{emoji} YENİ SİNYAL — {ticker} ({market.upper()})\n"
            f"Yön: {direction_tr}\n"
            f"Strateji: {strategy_name}\n"
            f"\n"
            f"Güncel: {current_price:.4f}\n"
            f"Giriş:  {entry_price:.4f}\n"
            f"Stop:   {stop_loss:.4f}\n"
            f"Hedef:  {take_profit:.4f}\n"
            f"Risk/Ödül: 1:{rr:.1f}\n"
            f"\n"
            f"⏳ Fiyat giriş seviyesine geldiğinde pozisyona girilebilir."
        )
        TelegramService.send(text)

    @staticmethod
    def send_signal_entered(
        ticker, market, direction, entry_price, stop_loss, take_profit, strategy_name=""
    ):
        """Notify when price reaches the entry level."""
        direction_tr = "LONG (Al)" if direction == "long" else "SHORT (Sat)"
        text = (
            f"✅ GİRİŞ SEVİYESİ — {ticker} ({market.upper()})\n"
            f"Yön: {direction_tr}\n"
            f"Strateji: {strategy_name}\n"
            f"\n"
            f"Giriş:  {entry_price:.4f}\n"
            f"Stop:   {stop_loss:.4f}\n"
            f"Hedef:  {take_profit:.4f}\n"
            f"\n"
            f"🚀 Pozisyona girilebilir. ⚠️ Stop loss'u unutma!"
        )
        TelegramService.send(text)
