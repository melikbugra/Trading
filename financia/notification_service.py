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

        thread = threading.Thread(target=EmailService._send_sync, args=(subject, body, to_email))
        thread.start()

    @staticmethod
    def _send_sync(subject, body, to_email):
        try:
            msg = MIMEMultipart()
            msg['From'] = SENDER_EMAIL
            msg['To'] = to_email
            msg['Subject'] = subject

            msg.attach(MIMEText(body, 'plain'))

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
