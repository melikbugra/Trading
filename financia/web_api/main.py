from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel
from typing import List, Optional
import threading
import time
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

# Database Imports
from financia.web_api.database import init_db, get_db, PortfolioItemDB, RecommendationDB, SessionLocal
from financia.get_model_decision import InferenceEngine
from financia.data_generator import BIST100

app = FastAPI(title="RL Trading Dashboard API")

# CORS Setup
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -- Models (Pydantic) --
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

# Global Engine
inference_engine = None
MODEL_PATH = "models/ppo_short_mid_agent"

@app.on_event("startup")
async def startup_event():
    global inference_engine
    
    # Initialize DB
    print("Initializing Database...")
    init_db()
    
    # Load Model
    print(f"Loading Model from {MODEL_PATH}...")
    inference_engine = InferenceEngine(MODEL_PATH)
    print("Model Loaded.")
    
    # Start Scheduler
    def scheduler_loop():
        time.sleep(10)
        while True:
            try:
                print("--- Scheduler: Starting Automatic Analysis ---")
                run_analysis_job_db()
                print("--- Scheduler: Finished. Sleeping for 15m ---")
            except Exception as e:
                print(f"Scheduler Error: {e}")
            time.sleep(900)
            
    thread = threading.Thread(target=scheduler_loop, daemon=True)
    thread.start()

# -- API Endpoints --

@app.get("/portfolio", response_model=List[PortfolioItem])
def get_portfolio(db: Session = Depends(get_db)):
    items = db.query(PortfolioItemDB).all()
    return items

@app.post("/portfolio")
def add_ticker(item: StockItem, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    ticker = item.ticker.upper()
    existing = db.query(PortfolioItemDB).filter(PortfolioItemDB.ticker == ticker).first()
    if existing:
        return {"message": f"{ticker} already exists."}
    
    new_item = PortfolioItemDB(
        ticker=ticker,
        last_decision="PENDING",
        last_updated="-"
    )
    db.add(new_item)
    db.commit()
    
    # Trigger analysis
    background_tasks.add_task(analyze_single_ticker_db, ticker)
    return {"message": f"{ticker} added."}

@app.delete("/portfolio/{ticker}")
def remove_ticker(ticker: str, db: Session = Depends(get_db)):
    ticker = ticker.upper()
    item = db.query(PortfolioItemDB).filter(PortfolioItemDB.ticker == ticker).first()
    if not item:
        raise HTTPException(status_code=404, detail="Ticker not found")
        
    db.delete(item)
    db.commit()
    return {"message": f"{ticker} removed."}

@app.post("/refresh")
def refresh_analysis(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_analysis_job_db)
    return {"message": "Analysis started in background."}

# -- Recommendations Endpoint --
@app.get("/recommendations", response_model=List[RecommendationItem])
def get_recommendations(limit: int = 5, db: Session = Depends(get_db)):
    # Order by Score DESC, then Divergence Count DESC
    items = db.query(RecommendationDB)\
              .order_by(RecommendationDB.score.desc(), RecommendationDB.divergence_count.desc())\
              .limit(limit).all()
    return items

@app.post("/recommendations/scan")
def scan_market(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_market_scanner)
    return {"message": "Market scan started. Check back in a few minutes."}

# -- Analysis Logic (Core) --
def analyze_single_ticker_core(ticker: str):
    """
    Common logic used by both Portfolio and Scanner.
    Returns the result dict or None.
    """
    global inference_engine
    if inference_engine is None: return None
    
    try:
        # Check cache or throttle? 
        # For now, just run.
        result = inference_engine.analyze_ticker(ticker, horizon='short-mid')
        return result
    except Exception as e:
        print(f"Core Analysis Error {ticker}: {e}")
        return None

from financia.notification_service import EmailService

def analyze_single_ticker_db(ticker: str):
    print(f"Analyzing Portfolio Item: {ticker}...")
    result = analyze_single_ticker_core(ticker)
    if not result: return

    try:
        db = SessionLocal()
        item = db.query(PortfolioItemDB).filter(PortfolioItemDB.ticker == ticker).first()
        
        if item:
            if "error" in result:
                item.last_decision = "ERROR"
            else:
                new_decision = result["decision"]
                old_decision = item.last_decision
                
                # Check for Alert Condition (Any Status Change)
                if old_decision != new_decision:
                    print(f"!!! TRIGGERING ALERT FOR {ticker}: {old_decision} -> {new_decision} !!!")
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
                # UTC+3
                item.last_updated = (datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
                item.final_score = result.get("final_score", 0.0)
                item.category_scores = result.get("category_scores", {})
                item.indicator_details = result.get("indicator_details", [])
            
            db.commit()
        db.close()
    except Exception as e:
        print(f"DB Update Error {ticker}: {e}")

def run_analysis_job_db():
    db = SessionLocal()
    tickers = [item.ticker for item in db.query(PortfolioItemDB).all()]
    db.close()
    
    for ticker in tickers:
        analyze_single_ticker_db(ticker)

# -- Market Scanner Logic --
def run_market_scanner():
    """
    Scans entire BIST100 list and updates RecommendationDB.
    Filters for BUY/STRONG BUY and positive Score.
    """
    print("--- Market Scanner Started ---")
    
    # Clean old recommendations? 
    # Or strict update? Let's clear table to keep it fresh top picks.
    db = SessionLocal()
    db.query(RecommendationDB).delete()
    db.commit()
    db.close()
    
    for ticker in BIST100:
        # Be nice to CPU/API
        # time.sleep(0.5) 
        
        result = analyze_single_ticker_core(ticker)
        
        if result and "error" not in result:
            decision = result["decision"]
            score = result.get("final_score", 0.0)
            
            # Filtering Criteria
            # 1. Must be BUY or STRONG BUY
            # 2. Score must be positive (> 50 implied by buy usually, but let's check score)
            if decision in ["BUY", "STRONG BUY"] and score >= 50:
                
                # Calculate Divergence Count
                details = result.get("indicator_details", [])
                # Divergence: 1 (Bullish), -1 (Bearish)
                div_count = sum(1 for d in details if d.get('Divergence', 0) == 1)
                
                # We prioritize those with divergences
                
                # Save to DB
                db = SessionLocal()
                rec = RecommendationDB(
                    ticker=ticker,
                    score=score,
                    decision=decision,
                    price=result["price"],
                    divergence_count=div_count,
                    last_updated=(datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
                )
                db.add(rec)
                db.commit()
                db.close()
                print(f"Scanner: Recommended {ticker} (Score: {score}, Div: {div_count})")
        
    print("--- Market Scanner Finished ---")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
