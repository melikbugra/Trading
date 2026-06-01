---
name: Teknik Analiz Project Overview
description: Multi-market algo trading platform with real-time scanning, simulation, and backtesting capabilities
type: project
---

**Core:** FastAPI backend + React (Vite) frontend for algorithmic trading signal generation and simulation.

**Key Components:**
- 4 trading strategies (EMA+MACD, Resistance+StochRSI, Inside Bar Breakout, VWAP Bounce)
- 30+ technical indicators in StockAnalyzer (analyzer.py, 2000+ lines)
- Real-time scanner with WebSocket broadcasting
- Simulation/backtesting engine with time replay and balance tracking
- EOD (end-of-day) analysis service for BIST100
- Email notification system
- SQLite database with 15+ tables (production + simulation mirrors)

**Current branch:** feature/algo-trade — indicates active development of algorithmic trading features.

**Why:** The user wants to test and deploy technical analysis strategies on BIST100 and Binance with full trade audit trail.

**How to apply:** Focus suggestions on trading logic correctness, strategy robustness, and production reliability.
