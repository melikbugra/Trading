"""
BIST100 API Router

Handles all BIST100 (Turkish Stock Exchange) related endpoints.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List

from financia.web_api.database import (
    get_db, SessionLocal,
    BIST100PortfolioItem, BIST100Recommendation
)
from financia.web_api.websocket_manager import manager
from financia.data_generator import BIST100

router = APIRouter(prefix="/bist100", tags=["BIST100"])

# Pydantic Models
from pydantic import BaseModel
from typing import Optional

class StockItem(BaseModel):
    ticker: str

class PortfolioItem(BaseModel):
    ticker: str
    last_decision: str
    last_price: float
    last_volume: Optional[float] = 0.0
    last_volume_ratio: Optional[float] = 0.0
    last_updated: str
    final_score: Optional[float] = 0.0
    category_scores: Optional[dict] = {}
    indicator_details: Optional[List[dict]] = []
    
    class Config:
        from_attributes = True

class RecommendationItem(BaseModel):
    ticker: str
    score: float
    decision: str
    price: float
    divergence_count: float
    last_updated: str
    
    class Config:
        from_attributes = True

class LiveModeSetting(BaseModel):
    enabled: bool

# Global settings for this market
bist100_live_mode = False

# -- Settings --
@router.get("/settings/live-mode")
def get_live_mode():
    return {"enabled": bist100_live_mode}

@router.post("/settings/live-mode")
def set_live_mode(setting: LiveModeSetting):
    global bist100_live_mode
    bist100_live_mode = setting.enabled
    mode_str = "LIVE (Real-time)" if bist100_live_mode else "STABLE (Closed Candles)"
    print(f"BIST100 Live Mode changed to: {mode_str}")
    return {"enabled": bist100_live_mode, "message": f"Mode set to {mode_str}"}

# -- Portfolio CRUD --
@router.get("/portfolio", response_model=List[PortfolioItem])
def get_portfolio(db: Session = Depends(get_db)):
    items = db.query(BIST100PortfolioItem).all()
    return items

@router.post("/portfolio")
def add_to_portfolio(item: StockItem, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    ticker = item.ticker.upper()
    if not ticker.endswith(".IS"):
        ticker += ".IS"
    
    existing = db.query(BIST100PortfolioItem).filter(BIST100PortfolioItem.ticker == ticker).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ticker already in portfolio")
    
    new_item = BIST100PortfolioItem(
        ticker=ticker,
        last_decision="PENDING",
        last_price=0.0,
        last_updated=(datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
    )
    db.add(new_item)
    db.commit()
    
    # Trigger analysis in background
    from financia.web_api.routers.bist100 import analyze_single_ticker_db
    background_tasks.add_task(analyze_single_ticker_db, ticker)
    
    return {"message": f"Added {ticker} to BIST100 portfolio", "ticker": ticker}

@router.delete("/portfolio/{ticker}")
def remove_from_portfolio(ticker: str, db: Session = Depends(get_db)):
    item = db.query(BIST100PortfolioItem).filter(BIST100PortfolioItem.ticker == ticker).first()
    if not item:
        raise HTTPException(status_code=404, detail="Ticker not found")
    
    db.delete(item)
    db.commit()
    return {"message": f"Removed {ticker} from BIST100 portfolio"}

@router.post("/portfolio/{ticker}/refresh")
def refresh_ticker(ticker: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    item = db.query(BIST100PortfolioItem).filter(BIST100PortfolioItem.ticker == ticker).first()
    if not item:
        raise HTTPException(status_code=404, detail="Ticker not found")
    
    background_tasks.add_task(analyze_single_ticker_db, ticker)
    return {"message": f"Refresh triggered for {ticker}"}

# -- Recommendations --
@router.get("/recommendations", response_model=List[RecommendationItem])
def get_recommendations(limit: int = 10, db: Session = Depends(get_db)):
    items = db.query(BIST100Recommendation)\
              .filter(BIST100Recommendation.decision.in_(["BUY", "STRONG BUY"]))\
              .order_by(BIST100Recommendation.score.desc(), BIST100Recommendation.divergence_count.desc())\
              .limit(limit).all()
    return items

@router.post("/recommendations/scan")
def scan_market(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_market_scanner)
    return {"message": "BIST100 market scan started."}

# -- Analysis Logic --
def get_engine():
    """Get the BIST100 inference engine from main app"""
    from financia.web_api.main import bist100_engine
    return bist100_engine

def analyze_single_ticker_core(ticker: str):
    engine = get_engine()
    if engine is None:
        print("BIST100 engine not loaded")
        return None
    
    try:
        result = engine.analyze_ticker(ticker, horizon='short', use_live=bist100_live_mode)
        return result
    except Exception as e:
        print(f"BIST100 Analysis Error {ticker}: {e}")
        return None

def analyze_single_ticker_db(ticker: str):
    print(f"[BIST100] Analyzing: {ticker}...")
    result = analyze_single_ticker_core(ticker)
    if not result:
        return

    try:
        db = SessionLocal()
        item = db.query(BIST100PortfolioItem).filter(BIST100PortfolioItem.ticker == ticker).first()
        
        if item:
            if "error" in result:
                item.last_decision = "ERROR"
            else:
                from financia.notification_service import EmailService
                
                new_decision = result["decision"]
                old_decision = item.last_decision
                
                if old_decision != new_decision and old_decision != "PENDING":
                    print(f"[BIST100] ALERT: {ticker}: {old_decision} -> {new_decision}")
                    EmailService.send_decision_alert(
                        ticker=ticker,
                        old_decision=old_decision,
                        new_decision=new_decision,
                        price=result["price"],
                        score=result.get("final_score", 0.0)
                    )
                
                item.last_decision = new_decision
                item.last_price = result["price"]
                item.last_volume = result.get("volume", 0.0)
                item.last_volume_ratio = result.get("volume_ratio", 0.0)
                item.last_updated = (datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
                item.final_score = result.get("final_score", 0.0)
                item.category_scores = result.get("category_scores", {})
                item.indicator_details = result.get("indicator_details", [])
            
            db.commit()
            
            # Broadcast via WebSocket
            try:
                import asyncio
                payload = {
                    "market": "bist100",
                    "ticker": item.ticker,
                    "last_decision": item.last_decision,
                    "last_price": item.last_price,
                    "last_volume": item.last_volume,
                    "last_volume_ratio": item.last_volume_ratio,
                    "last_updated": item.last_updated,
                    "final_score": item.final_score,
                    "category_scores": item.category_scores,
                    "indicator_details": item.indicator_details
                }
                loop = asyncio.new_event_loop()
                loop.run_until_complete(manager.broadcast({"type": "PORTFOLIO_UPDATE", "data": payload}))
                loop.close()
            except Exception as e:
                print(f"WS Broadcast error: {e}")
                
        db.close()
    except Exception as e:
        print(f"[BIST100] DB Error for {ticker}: {e}")

def run_market_scanner():
    print("[BIST100] Starting Market Scanner...")
    
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        loop.run_until_complete(manager.broadcast({"type": "SCAN_STARTED", "data": {"market": "bist100"}}))
        loop.close()
    except:
        pass
    
    db = SessionLocal()
    
    for ticker in BIST100:
        try:
            result = analyze_single_ticker_core(ticker)
            if result and "error" not in result:
                existing = db.query(BIST100Recommendation).filter(BIST100Recommendation.ticker == ticker).first()
                
                if existing:
                    existing.score = result.get("final_score", 0.0)
                    existing.decision = result.get("decision", "HOLD")
                    existing.price = result.get("price", 0.0)
                    existing.divergence_count = result.get("divergence_count", 0)
                    existing.last_updated = (datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    new_rec = BIST100Recommendation(
                        ticker=ticker,
                        score=result.get("final_score", 0.0),
                        decision=result.get("decision", "HOLD"),
                        price=result.get("price", 0.0),
                        divergence_count=result.get("divergence_count", 0),
                        last_updated=(datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
                    )
                    db.add(new_rec)
                
                db.commit()
        except Exception as e:
            print(f"[BIST100] Scanner error for {ticker}: {e}")
    
    db.close()
    
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        loop.run_until_complete(manager.broadcast({"type": "SCAN_COMPLETED", "data": {"market": "bist100"}}))
        loop.close()
    except:
        pass
    
    print("[BIST100] Market Scanner Complete.")

def run_analysis_job():
    """Background job to analyze all portfolio items"""
    db = SessionLocal()
    items = db.query(BIST100PortfolioItem).all()
    db.close()
    
    for item in items:
        analyze_single_ticker_db(item.ticker)
