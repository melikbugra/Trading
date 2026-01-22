"""
RL Trading Dashboard API

Multi-market support for BIST100 and Binance.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import threading
import time
from datetime import datetime, timedelta

# Database & State Imports
from financia.web_api.database import init_db, SessionLocal
from financia.get_model_decision import InferenceEngine
from financia.web_api.websocket_manager import manager
from financia.web_api.state import state

# Routers
from financia.web_api.routers import bist100, binance, recommendations

app = FastAPI(
    title="RL Trading Dashboard API",
    version="2.0.0",
    redirect_slashes=False,  # Prevent 307 redirects that break HTTPS
)

# CORS Setup
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Market-Specific Routers
app.include_router(bist100.router)
app.include_router(binance.router)
app.include_router(recommendations.router)

# Model Paths
BIST100_MODEL_PATH = "bist100_models/bist100_ppo_short_agent"
BINANCE_MODEL_PATH = "binance_models/binance_ppo_short_agent"


@app.on_event("startup")
async def startup_event():
    # Print all routes for debugging
    print("Registered Routes:")
    for route in app.routes:
        print(f" - {route.path} ({getattr(route, 'methods', 'WS')})")

    # Initialize DB
    print("Initializing Database...")
    init_db()

    # Load BIST100 Model
    print(f"Loading BIST100 Model from {BIST100_MODEL_PATH}...")
    try:
        state.bist100_engine = InferenceEngine(BIST100_MODEL_PATH)
        if state.bist100_engine.load_model():
            print("BIST100 Model Loaded and Ready.")
        else:
            print("BIST100 Model failed to load.")
            state.bist100_engine = None
    except Exception as e:
        print(f"BIST100 Model not available: {e}")

    # Load Binance Model (if available)
    print(f"Checking Binance Model at {BINANCE_MODEL_PATH}...")
    import os

    if os.path.exists(f"{BINANCE_MODEL_PATH}.ckpt"):
        try:
            state.binance_engine = InferenceEngine(BINANCE_MODEL_PATH)
            if state.binance_engine.load_model():
                print("Binance Model Loaded and Ready.")
            else:
                print("Binance Model failed to load.")
                state.binance_engine = None
        except Exception as e:
            print(f"Binance Model load error: {e}")
    else:
        print("Binance Model not trained yet. Skipping.")

    # Start Background Schedulers
    def bist100_scheduler():
        """BIST100 market hours scheduler (09:00-18:30 Turkish time, weekdays)"""
        time.sleep(10)
        while True:
            try:
                now_utc = datetime.utcnow()
                now_tr = now_utc + timedelta(hours=3)

                hour = now_tr.hour
                weekday = now_tr.weekday()

                market_open = (hour >= 9) and (
                    (hour < 18) or (hour == 18 and now_tr.minute <= 30)
                )
                is_weekday = weekday < 5

                if market_open and is_weekday:
                    print(
                        f"[BIST100 Scheduler] Market Open ({now_tr.strftime('%H:%M')}) - Running Analysis..."
                    )
                    bist100.run_analysis_job()
                    time.sleep(60)  # Run every minute during market hours
                else:
                    time.sleep(300)  # 5 min sleep when market closed

            except Exception as e:
                print(f"[BIST100 Scheduler] Error: {e}")
                time.sleep(300)

    def binance_scheduler():
        """Binance 24/7 scheduler (crypto never sleeps)"""
        time.sleep(15)
        while True:
            try:
                if state.binance_engine is not None:
                    print("[Binance Scheduler] Running Analysis...")
                    binance.run_analysis_job()
                time.sleep(60)  # Every minute for crypto
            except Exception as e:
                print(f"[Binance Scheduler] Error: {e}")
                time.sleep(60)

    # Start threads
    threading.Thread(target=bist100_scheduler, daemon=True).start()
    threading.Thread(target=binance_scheduler, daemon=True).start()


# -- WebSocket Endpoint --
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo or handle commands if needed
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/ws-status")
def ws_status_check():
    """Debug endpoint to check if /ws is reachable via HTTP."""
    return {"status": "ok", "message": "Use WebSocket protocol to connect to /ws"}


# -- Health Check --
@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "bist100_engine": state.bist100_engine is not None,
        "binance_engine": state.binance_engine is not None,
    }


# -- Available Markets Info --
@app.get("/markets")
def list_markets():
    return {
        "markets": [
            {
                "id": "bist100",
                "name": "BIST100 (Turkish Stocks)",
                "currency": "TRY",
                "timezone": "UTC+3",
                "hours": "09:00-18:30 (Weekdays)",
                "model_ready": state.bist100_engine is not None,
            },
            {
                "id": "binance",
                "name": "Binance (Crypto)",
                "currency": "USDT",
                "timezone": "UTC",
                "hours": "24/7",
                "model_ready": state.binance_engine is not None,
            },
        ]
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
