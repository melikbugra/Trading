from fastapi import APIRouter, BackgroundTasks, HTTPException
from typing import List, Optional
from pydantic import BaseModel
import asyncio
import random
import pandas as pd
from datetime import datetime

# Import internal modules (Adjust paths as needed)
from financia.analyzer import StockAnalyzer
from financia.indicator_config import TIMEFRAME_INTERVALS
from financia.web_api.websocket_manager import manager

router = APIRouter(
    prefix="/recommendations",
    tags=["recommendations"]
)

# In-memory cache for recommendations
recommendation_cache = []

class RecommendationItem(BaseModel):
    ticker: str
    decision: str
    score: float
    divergence_count: int
    price: float
    last_updated: str

@router.get("/", response_model=List[RecommendationItem])
async def get_recommendations():
    return recommendation_cache

async def run_market_scan(market: str = 'bist100'):
    """
    Background task to scan BIST100 or Binance market.
    """
    global recommendation_cache
    
    # We might want to keep caches separate or just filter in frontend?
    # For now, let's clear only if we assume single-user/single-view focus, 
    # but strictly speaking we should probably append or manage by market.
    # To keep it simple for the UI (which expects a full list), let's clear.
    recommendation_cache = [r for r in recommendation_cache if r.get('market') != market]
    
    tickers = []
    if market == 'bist100':
        tickers = [
            "AEFES.IS", "AGHOL.IS", "AKBNK.IS", "AKCNS.IS", "AKFGY.IS", "AKSA.IS", "AKSEN.IS",
            "ALARK.IS", "ALBRK.IS", "ALFAS.IS", "ANHYT.IS", "ARCLK.IS", "ASELS.IS", "ASTOR.IS",
            "ASUZU.IS", "AYDEM.IS", "BAGFS.IS", "BASGZ.IS", "BERA.IS", "BIMAS.IS", "BIOEN.IS",
            "BOBET.IS", "BRSAN.IS", "BRYAT.IS", "BUCIM.IS", "CANTE.IS", "CCOLA.IS", "CEMTS.IS",
            "CIMSA.IS", "DOHOL.IS", "DOAS.IS", "ECILC.IS", "ECZYT.IS", "EGEEN.IS",
            "EKGYO.IS", "ENJSA.IS", "ENKAI.IS", "EREGL.IS", "EUREN.IS", "FENER.IS",
            "FROTO.IS", "GARAN.IS", "GENIL.IS", "GESAN.IS", "GLYHO.IS", "GSDHO.IS", "GUBRF.IS",
            "GWIND.IS", "HALKB.IS", "HEKTS.IS", "IPEKE.IS", "ISCTR.IS", "ISDMR.IS", "ISFIN.IS",
            "ISGYO.IS", "ISMEN.IS", "KCAER.IS", "KCHOL.IS", "KONTR.IS", "KONYA.IS",
            "KORDS.IS", "KOZAL.IS", "KOZAA.IS", "KRDMD.IS", "KZBGY.IS", "MAVI.IS", "MGROS.IS",
            "MIATK.IS", "ODAS.IS", "OTKAR.IS", "OYAKC.IS", "PENTA.IS", "PETKM.IS", "PGSUS.IS",
            "PSGYO.IS", "QUAGR.IS", "SAHOL.IS", "SASA.IS", "SAYAS.IS", "SDTTR.IS", "SISE.IS",
            "SKBNK.IS", "SMRTG.IS", "SOKM.IS", "TAVHL.IS", "TCELL.IS", "THYAO.IS", "TKFEN.IS",
            "TOASO.IS", "TSKB.IS", "TTKOM.IS", "TTRAK.IS", "TUKAS.IS", "TUPRS.IS", "TURSG.IS",
            "ULKER.IS", "VAKBN.IS", "VESBE.IS", "VESTL.IS", "YEOTK.IS", "YKBNK.IS", "YYLGD.IS",
            "ZOREN.IS"
        ]
    elif market == 'binance':
        tickers = [
            "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT",
            "ADA/USDT", "AVAX/USDT", "DOGE/USDT", "TRX/USDT", "DOT/USDT",
            "MATIC/USDT", "LINK/USDT", "SHIB/USDT", "LTC/USDT", "UNI/USDT"
        ]
    
    print(f"Starting {market.upper()} market scan for {len(tickers)} tickers...")
    
    for ticker in tickers:
        try:
            # Configure Analyzer for correct market
            # Binance uses 1h timeframe for 'short' horizon as per updated config
            analyzer = StockAnalyzer(ticker, horizon='short', period='10d', interval='1h', market=market)
            
            if analyzer.data is None or analyzer.data.empty:
                continue
                
            last_close = analyzer.data['Close'].iloc[-1]
            
            # Todo: AI Inference here
            score = random.uniform(50, 95)
            decision = "BUY" if score > 70 else "HOLD"
            if score > 85: decision = "STRONG BUY"
            
            div_count = random.randint(0, 2)
            
            if decision == "HOLD":
                continue # Only send interesting things
                
            rec = {
                "ticker": ticker,
                "market": market,
                "decision": decision,
                "score": score,
                "divergence_count": div_count,
                "price": float(last_close),
                "last_updated": datetime.now().strftime("%H:%M")
            }
            
            recommendation_cache.append(rec)
            
            # Broadcast via WebSocket
            await manager.broadcast({
                "type": "RECOMMENDATION_UPDATE",
                "data": rec
            })
            
            # Small delay
            await asyncio.sleep(0.5)
            
        except Exception as e:
            print(f"Error scanning {ticker}: {e}")
            continue

    # Notify Finish
    await manager.broadcast({
        "type": "SCAN_FINISHED",
        "data": {"count": len(recommendation_cache), "market": market}
    })
    print(f"{market.upper()} scan finished.")

@router.post("/scan")
async def start_scan(background_tasks: BackgroundTasks, market: str = 'bist100'):
    background_tasks.add_task(run_market_scan, market)
    return {"status": "Scan started", "market": market}
