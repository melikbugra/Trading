# Teknik Analiz — Codex project context

## Project

Strategy-based trading dashboard for BIST100 and Binance. The backend is Python 3.11+ with FastAPI, pandas, yfinance, ccxt and SQLAlchemy. The frontend is React 19/Vite/Tailwind in `financia/ui`.

## Structure

- `financia/analyzer.py`: market data loading and technical indicators.
- `financia/strategies/`: rule-based strategies and strategy registry.
- `financia/scanner.py`: live scanner and signal generation.
- `financia/simulation_scanner.py`: historical simulation/backtest engine.
- `financia/eod_service.py`: end-of-day analysis and scheduler.
- `financia/fundamental_service.py`: yfinance fundamentals, news and scoring.
- `financia/markets.py` / `indicator_config.py`: market and indicator configuration.
- `financia/web_api/`: FastAPI app, routers, WebSocket and SQLAlchemy models.
- `financia/ui/src/`: dashboard UI; API base URL is configured with `VITE_API_URL`.
- `data/`: runtime database/data; treat as user data.

## Run

```bash
./dev.sh
```

Backend only:

```bash
poetry run uvicorn financia.web_api.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend only:

```bash
cd financia/ui && npm run dev -- --host
```

Useful checks:

```bash
poetry run python -c "import financia.simulation_scanner, financia.scanner, financia.eod_service, financia.analyzer, financia.fundamental_service; print('imports OK')"
cd financia/ui && npm run lint && npm run build
```

## Important invariants

- Do not use an in-progress candle for signals. BIST Yahoo data is delayed by about 15 minutes; Binance is real-time and must not inherit BIST delay.
- Market IDs are inconsistent in older code (`bist`, `bist100`, `bist100...`); use the existing normalization helpers in `markets.py` before adding new branching.
- Simulation has separate database models/state from live trading. Keep live and simulation behavior isolated.
- Strategy parameters are persisted as JSON in the database; preserve existing API response shapes and frontend field names.
- Trading calculations should handle missing/NaN provider data without crashing. External yfinance/ccxt calls may be slow or unavailable.
- Do not modify, delete, or commit runtime data, credentials, logs, `__pycache__`, or model directories unless explicitly requested.

## Working rules

- Read the relevant module and router/component before editing; keep changes narrow.
- Prefer existing helpers and conventions over introducing a second implementation.
- After Python changes, run the import check; after UI changes, run lint/build when practical.
- There is currently no dedicated automated test suite in the repository, so report checks performed and any unverified external-data behavior.
- Existing `CLAUDE.md` files contain claude-mem activity markers, not authoritative project instructions; preserve them unless the user asks for cleanup.

## Current handoff

- Branch: `feature/algo-trade`.
- Working tree was clean when this context was created.
- HEAD is `6dce2d9`; the latest work adjusted delayed-bar handling, Wilder ADX/DMI, dividend-yield normalization and market-aware fundamental scoring.
