import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import threading

# Configuration
try:
    from financia.email_config import SMTP_CONFIG

    SMTP_SERVER = SMTP_CONFIG.get("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = SMTP_CONFIG.get("SMTP_PORT", 587)
    SENDER_EMAIL = SMTP_CONFIG.get("SENDER_EMAIL", "")
    SENDER_PASSWORD = SMTP_CONFIG.get("SENDER_PASSWORD", "")
    RECIPIENT_EMAIL = SMTP_CONFIG.get("RECIPIENT_EMAIL", "melikbugraozcelik2@gmail.com")
except ImportError:
    # Fallback to Env Vars
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    SENDER_EMAIL = os.getenv("SENDER_EMAIL", "sizinepostaniz@gmail.com")
    SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")
    RECIPIENT_EMAIL = "melikbugraozcelik2@gmail.com"


class EmailService:
    @staticmethod
    def send_email(subject, body, to_email=RECIPIENT_EMAIL):
        """
        Sends an email in a background thread to avoid blocking the main app.
        """
        # Validate credentials first to avoid useless thread spawn if not configured
        if "sizinepostaniz" in SENDER_EMAIL or "uygulama_sifresi" in SENDER_PASSWORD:
            print("[EmailService] Skipping email: Credentials not set.")
            return

        thread = threading.Thread(
            target=EmailService._send_sync, args=(subject, body, to_email)
        )
        thread.start()

    @staticmethod
    def _send_sync(subject, body, to_email):
        try:
            msg = MIMEMultipart()
            msg["From"] = SENDER_EMAIL
            msg["To"] = to_email
            msg["Subject"] = subject

            msg.attach(MIMEText(body, "plain"))

            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            text = msg.as_string()
            server.sendmail(SENDER_EMAIL, to_email, text)
            server.quit()
            print(f"[EmailService] Email sent to {to_email}")
        except Exception as e:
            print(f"[EmailService] Failed to send email: {e}")

    @staticmethod
    def send_decision_alert(ticker, old_decision, new_decision, price, score):
        # Determine emoji based on decision
        emoji = "ℹ️"
        if "SELL" in new_decision:
            emoji = "🚨"
        elif "BUY" in new_decision:
            emoji = "🟢"

        subject = f"{emoji} Signal Update: {ticker} ({old_decision} ➡️ {new_decision})"

        body = f"""
        RL Trading Bot Signal Check
        
        TICKER:   {ticker}
        CHANGE:   {old_decision}  ➡️  {new_decision}
        PRICE:    {price:.2f} ₺
        SCORE:    {score:.2f}
        
        The technical decision for this stock has changed.
        
        Dashboard: http://localhost:5173
        """
        EmailService.send_email(subject, body)

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
        """Send email when a new signal is triggered."""
        emoji = "🟢" if direction == "long" else "🔴"
        direction_tr = "LONG (Al)" if direction == "long" else "SHORT (Sat)"

        # Calculate R:R
        if direction == "long":
            risk = entry_price - stop_loss
            reward = take_profit - entry_price
        else:
            risk = stop_loss - entry_price
            reward = entry_price - take_profit
        rr = reward / risk if risk > 0 else 0

        subject = f"{emoji} YENİ SİNYAL: {ticker} {direction_tr}"

        body = f"""
🎯 YENİ TETİKLENEN SİNYAL
{"=" * 40}

Sembol:       {ticker} ({market.upper()})
Yön:          {direction_tr}
Strateji:     {strategy_name}

💰 FİYAT SEVİYELERİ
{"=" * 40}
Güncel Fiyat: {current_price:.4f}
Giriş Fiyatı: {entry_price:.4f}
Stop Loss:    {stop_loss:.4f}
Kar Hedefi:   {take_profit:.4f}
Risk/Ödül:    1:{rr:.1f}

⏳ Fiyat giriş seviyesine geldiğinde pozisyona girilebilir.

Dashboard: http://localhost:5173
        """
        EmailService.send_email(subject, body)

    @staticmethod
    def send_signal_entered(
        ticker, market, direction, entry_price, stop_loss, take_profit, strategy_name=""
    ):
        """Send email when price hits entry level."""
        emoji = "✅"
        direction_tr = "LONG (Al)" if direction == "long" else "SHORT (Sat)"

        subject = f"{emoji} POZİSYONA GİR: {ticker} {direction_tr} @ {entry_price:.4f}"

        body = f"""
✅ GİRİŞ SEVİYESİNE ULAŞILDI!
{"=" * 40}

Sembol:       {ticker} ({market.upper()})
Yön:          {direction_tr}
Strateji:     {strategy_name}

🚀 POZİSYONA GİRİLEBİLİR!
{"=" * 40}
Giriş Fiyatı: {entry_price:.4f}
Stop Loss:    {stop_loss:.4f}
Kar Hedefi:   {take_profit:.4f}

⚠️  Stop loss seviyesini unutma!

Dashboard: http://localhost:5173
        """
        EmailService.send_email(subject, body)
