from financia.notification_service import EmailService
import time

print("--- Testing Email Service ---")
print("Attempting to send a test email...")

try:
    # Trigger a fake alert
    EmailService.send_sell_alert(
        ticker="TEST.IS",
        decision="STRONG SELL",
        price=123.45,
        score=25.0
    )
    
    # Wait a bit because the service uses a background thread
    print("Email task submitted. Waiting for background thread execution...")
    time.sleep(5)
    print("Done.")

except Exception as e:
    print(f"Test script crashed: {e}")
