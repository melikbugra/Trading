"""
Strategy-Based Trading Dashboard API

Multi-market support for BIST100 and Binance.
Rule-based strategy system with signal generation.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from contextlib import asynccontextmanager

# Database & State Imports
from financia.web_api.database import init_db, SessionLocal, ScannerConfig
from financia.web_api.websocket_manager import manager
from financia.scanner import scanner
from financia.eod_service import eod_service

# Routers
from financia.web_api.routers import strategies


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    # Startup
    print("=" * 50)
    print("Strategy Trading Dashboard - Starting Up")
    print("=" * 50)

    # Print all routes for debugging
    print("\nRegistered Routes:")
    for route in app.routes:
        print(f" - {route.path} ({getattr(route, 'methods', 'WS')})")

    # Initialize DB
    print("\nInitializing Database...")
    init_db()

    # Connect scanner to WebSocket manager for broadcasting
    scanner.set_ws_manager(manager)

    # Load scanner config and auto-start if enabled
    db = SessionLocal()
    try:
        config = db.query(ScannerConfig).first()
        if config and config.is_running:
            scanner.set_interval(config.scan_interval_minutes)
            await scanner.start()
            print(
                f"\n[Scanner] Auto-started with {config.scan_interval_minutes} min interval"
            )
    finally:
        db.close()

    # Start EOD analysis scheduler (runs at 18:15 Turkey time)
    await eod_service.start()
    print("[EOD] Scheduler started - will run at 18:15 on weekdays")

    print("\n✅ System Ready!")
    print("=" * 50)

    yield  # App is running

    # Shutdown
    print("\nShutting down services...")
    await scanner.stop()
    await eod_service.stop()
    print("Goodbye!")


app = FastAPI(
    title="Strategy Trading Dashboard API",
    version="3.0.0",
    redirect_slashes=False,  # Prevent 307 redirects that break HTTPS
    lifespan=lifespan,
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

# Include Strategy Router
app.include_router(strategies.router)


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
        "scanner_running": scanner.is_running,
        "scan_interval_minutes": scanner.scan_interval,
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
            },
            {
                "id": "binance",
                "name": "Binance (Crypto)",
                "currency": "TRY",
                "timezone": "UTC",
                "hours": "24/7",
            },
        ]
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
