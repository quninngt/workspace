# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

Backend and frontend fully implemented. Signal engine is operational. Data collection from 天天基金 public APIs is ongoing. The authoritative specification document is `PRD-v2.md`.

**Key metrics (as of 2026-05-22):** ~26,700 total funds in DB, 13,696 funds with NAV data, 1.65M NAV records (~130 records/fund, ~6 months), signal engine produces ~13,407 signals daily across A/B/C levels.

## Project Goal

Cumbre — 基金智投跟投平台. China-focused fund investment platform. Multi-factor signal engine generates daily Buy/Sell/Hold signals. Dual-mode execution: auto mode (model validation) and manual mode (user-driven decisions).

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python + FastAPI (uvicorn, `--reload`) |
| Frontend | React 19 + TypeScript + Vite 6 + TailwindCSS 3 + Recharts 2 |
| Database | SQLite via SQLAlchemy 2.0 async (dev) / MySQL (prod) |
| Auth | JWT (python-jose + bcrypt) |
| ORM | SQLAlchemy 2.0 async (aiosqlite) |
| Data collection | httpx + APScheduler (daily 20:30, weekly Sun 21:00 Beijing) |
| Signal engine | Python, runs as part of the API process |
| Charts | Recharts (LineChart, PieChart) |

## Project Structure

```
/
├── PRD-v2.md                # Product requirements (source of truth)
├── TODO.md                  # Task tracking
├── TEST.md                  # System test document (30 test cases)
├── package.json             # Monorepo root (npm workspace: client)
├── backend/
│   ├── .env                 # DATABASE_URL, JWT_SECRET
│   ├── requirements.txt
│   ├── cumbre.db            # SQLite database (auto-created)
│   ├── populate_demo.py     # Standalone batch sync script (legacy)
│   ├── run_batch_sync.py    # Batch NAV sync with progress reporting (BATCH=200, CONCURRENCY=12)
│   └── app/
│       ├── main.py          # FastAPI entry: lifespan (init_db, start_scheduler), CORS
│       ├── config.py        # Pydantic Settings from .env
│       ├── database.py      # SQLAlchemy async engine + sessionmaker + Base
│       ├── models/          # 7 modules: user, fund, signal, auto, manual, watchlist, backtest
│       ├── schemas/         # Pydantic v2 request/response models
│       ├── routers/         # 10 route modules, explicitly listed in __init__.py
│       └── services/
│           ├── auth.py              # bcrypt + JWT create/decode
│           ├── dependencies.py      # get_current_user FastAPI dep
│           ├── scheduler.py         # APScheduler (daily 20:30, Sun 21:00 Asia/Shanghai)
│           ├── auto_executor.py     # Auto trade execution engine
│           ├── manual_executor.py   # Manual submit-execution logic
│           ├── data_collector/
│           │   ├── collector.py     # Orchestrator (two-phase: concurrent fetch, sequential write)
│           │   ├── fund_list.py     # eastmoney JS API → fund list + detail
│           │   ├── fund_nav.py      # Two NAV sources: lsjz (incremental) + pingzhongdata (fallback)
│           │   ├── fund_holdings.py # eastmoney HTML holdings (JS content parsing)
│           │   ├── index_quota.py   # Tencent qt.gtimg.cn → index PE/PB + percentile
│           │   ├── adaptive_sync.py # Adaptive sync executor (dynamic concurrency/batch tuning)
│           │   └── scripts/         # Ad-hoc sync/test scripts
│           ├── signal_engine/
│           │   ├── engine.py        # Orchestrator: load NAV, run factors, save signals
│           │   ├── scorer.py        # Weighted combination → score → level (S/A/B/C/D)
│           │   └── factors/
│           │       ├── valuation.py # NAV-based proxy (no individual fund PE/PB available)
│           │       ├── trend.py     # MA20/MA60 crossover, price deviation
│           │       ├── momentum.py  # RSI + MACD
│           │       ├── quality.py   # Fund size, max drawdown
│           │       └── sentiment.py # Contrarian: volatility-based
│           └── backtesting/
│               └── backtester.py    # Batch NAV loading, configurable params, DB-persisted results
└── client/
    ├── package.json
    ├── vite.config.ts       # Proxy /api → localhost:8000, host: '0.0.0.0'
    ├── tailwind.config.js   # Custom primary color palette
    └── src/
        ├── main.tsx         # App entry, BrowserRouter + AuthProvider
        ├── App.tsx          # Routes (12 pages, protected via ProtectedRoute wrapper)
        ├── index.css        # Tailwind directives + base styles
        ├── api/client.ts    # Axios instance + typed API endpoint groups (10 groups)
        ├── context/AuthContext.tsx  # Auth state + login/register/logout
        ├── components/
        │   ├── Layout.tsx    # Sidebar + Outlet
        │   ├── Sidebar.tsx   # Nav items with lucide-react icons
        │   ├── charts/       # Chart sub-components (empty — Recharts used inline in pages)
        │   └── ui/           # Shared primitives: Button.tsx, Modal.tsx
        └── pages/ (13 pages, listed in FRONTEND ROUTING section)
```

## Architecture

```            
宏观信号 (PE/PB百分位) → risk_on/neutral/risk_off → 评分折扣
                                                    ↓
信号引擎 (全市场评分 × 宏观折扣) → 信号池 → 执行清单 (日投/周投/月投)
                                        ↓
                              ┌─────────┴─────────┐
                              ▼                   ▼
                          自动模式             手动模式
                      (不可编辑,自动执行)    (可增删改,确认提交)
                              ▼                   ▼
                          自动模拟组合          手动模拟组合
                              ▼
                          收益分析报告
```

**Current factor weights** (set in `scorer.py`): valuation 15%, trend 10%, momentum 30%, quality 30%, sentiment 15%. The PRD-v2.md and `scorer.py` docstring are **stale** (show old 40/25/15/10/10) — refer to the actual `FACTOR_WEIGHTS` dict in `scorer.py` for ground truth.

### Macro Signal Module

**File:** `backend/app/services/signal_engine/macro.py`

Determines market environment based on CSI 300 (沪深300) PE/PB percentiles:
- **risk_on** (PE百分位 < 30%): multiplier ×1.0 — 市场低估，满额评分
- **neutral** (30%-70%): multiplier ×0.92 — 中性环境，轻度折扣
- **risk_off** (PE百分位 > 70%): multiplier ×0.75 — 市场高估，大幅折扣

注意：数据库中 PE/PB 百分位以百分比存储（35.0 = 35%），不是小数。

**API:** `GET /api/macro-signal?date=YYYY-MM-DD`

**Integration:** Signal engine applies multiplier to ALL fund scores after z-score normalization.

### Risk Metrics Module

**File:** `backend/app/services/signal_engine/risk.py`

Calculates risk profile for individual funds from NAV history:
- **Annualized Volatility**: `daily_returns.std() × √252`
- **95% VaR**: `daily_returns.quantile(0.05)` — 95% 置信度下的最大日亏损
- **Sharpe Ratio**: `(annualized_return - risk_free_rate) / volatility`，无风险利率取 2%（1年期国债）
- **Max Drawdown**: 最大回撤百分比 + 回撤恢复天数
- **Risk Level**: 低风险 (< 10%)、中风险 (10-20%)、高风险 (> 20%)

**API:** `GET /api/funds/{code}/risk`

**Integration:** Signal engine stores risk_metrics in `factors_detail` JSON for each signal.

### Backtest Enhancement

**File:** `backend/app/services/backtesting/backtester.py`

Enhanced backtest with realistic trading costs:
- **申购费 (Subscription Fee)**: 0.15% per buy (天天基金标准费率)
- **赎回费 (Redemption Fee)**: 持有 < 7天 1.5%, 7-365天 0.5%, > 1年 0%
- **滑点 (Slippage)**: 0.05% per trade

Additional metrics:
- **Excess Return**: portfolio_return - benchmark_return
- **Information Ratio**: excess_return / tracking_error
- **Profit/Loss Ratio**: avg_profit / avg_loss
- **Total Trading Cost**: 申购费 + 赎回费 + 滑点

**API:** `POST /api/admin/backtest` with `params.trading_cost_ratio`, `params.subscription_fee`, etc.

### Data Flow

1. **Data Collection**: 天天基金 APIs → Fund/FundNav/FundHolding tables
2. **Signal Generation**: NAV data → 5 factor scorers → combined score → Signal table
3. **Execution**: Signals → ExecutionItem (generate-from-signals) → Auto/Manual portfolio

### NAV Sync Strategy

**Primary source — rankhandler batch API** (`fund.eastmoney.com/data/rankhandler.aspx`):
- 4 requests (`ft=gp`, `ft=zs`, `ft=hh p1`, `ft=hh p2`) = 13,674 funds with latest NAV + fund_size
- `sc=njjgm` sorts by fund size descending
- `pn=5000` returns up to 5000 per page
- Used for daily "what's outdated" check and fund list sync

**Per-fund NAV history** (only for outdated/new funds):
- `api.fund.eastmoney.com/f10/lsjz` with `startDate=6months_ago` for first-time sync (3 requests/fund, ~0.5s, returns up to 150 records)
- Same `lsjz` API with `startDate=latest_DB_date` for daily incremental (1 request/fund, ~0.17s)
- `pingzhongdata/{code}.js` used as fallback if lsjz returns no data (1 request = full history)

**First-sync optimization:** Only fetches last ~6 months (130 records max per fund) instead of full history (~5000 records). Saves ~96% network data and ~20% sync time.

**Daily flow (run_daily_collection):**
1. rankhandler 4 requests (~5s) → latest NAV for all 13K relevant funds
2. Compare with DB `MAX(date)` → identify outdated funds
3. Only fetch NAV history for outdated funds via lsjz concurrent
4. Sequential DB writes per batch (SQLite constraint)
5. Sync index quotas (PE/PB from Tencent API)

**Weekly flow (full_sync_job, Sunday 21:00):**
1. rankhandler fund list sync → update fund list + fund_size
2. Daily incremental NAV check (same as daily flow)
3. Index quota sync
4. Signal engine + auto executor

Only fund types `stock`, `mixed`, `index` are synced (RELEVANT_TYPES in collector.py).

### Router Registration Pattern

Routers are NOT auto-discovered — they are **explicitly imported and listed** in `backend/app/routers/__init__.py`. To add a new router, create the module, import it in `__init__.py`, and append to the `routers` list.

### Auth Dependencies

- `get_current_user` — standard JWT auth dependency, returns `User` object
- `get_admin_user` — extends `get_current_user`, raises 403 if `user.is_admin` is False. Used by admin endpoints (sync, signals, backtest, tools)

### Frontend API Pattern

API calls are centralized in `client/src/api/client.ts` as grouped objects (authApi, fundsApi, signalsApi, etc.) on a configured Axios instance. The interceptor attaches JWT from localStorage and handles 401 by redirecting to `/login`. No automatic token refresh exists.

## Data Models (19 tables)

### Core
- **User**: id, name, email, password_hash, is_admin(bool), created_at
- **Fund**: code (PK), name, type (stock/mixed/bond/index/etf/qdii/etc.), company, fund_size, risk_level
- **FundNav**: fund_code, date, nav, acc_nav — unique constraint on (fund_code, date)
- **FundValuation**: fund_code, date, pe, pb, pe_percentile, pb_percentile
- **FundHolding**: fund_code, stock_code, stock_name, ratio, date
- **FundManager**: id, name, description, tenure, fund_codes
- **IndexQuota**: index_code, name, pe, pb, pe_percentile, pb_percentile, date

### Signal
- **Signal**: id, fund_code, date, score(0-100), level(S/A/B/C/D), action(buy/hold/sell), factors_detail(JSON), created_at

### Execution
- **ExecutionItem**: user_id, plan_type, fund_code, action, status(pending/executed/skipped), suggested_amount
- **AutoConfig**: id, user_id, total_amount, daily_amount, plan_type, status, last_executed_at
- **AutoPortfolio/AutoPosition/AutoTrade/AutoReport**: user's auto portfolio
- **ManualPortfolio/ManualPosition/ManualTrade**: user's manual portfolio

### User
- **Watchlist**: user_id, fund_code, group_name

### Backtest
- **BacktestResult**: id, name, start_date, end_date, params(JSON), performance(JSON), signal_distribution(JSON), factor_contributions(JSON), monthly_returns(JSON), daily_values(JSON), summary(JSON), created_at

## Signal System

**Coverage:** 13,179 signals daily (all funds with ≥60 NAV records). Excludes 316 recently-established funds without enough trading days.

**Distribution (2026-05-18):** A: 15, B: 12,673, C: 491. Score range 28-72, avg 50.0, std 5.6. No S(≥80) or D(<25) levels with current market conditions.

Levels: S ≥80 (强买入), A 65-79 (买入), B 40-64 (持有), C 25-39 (卖出), D <25 (强卖出).

Factor weights (from `scorer.py`):
| Factor | Weight | What it measures |
|---|---|---|
| valuation | 15% | NAV-based proxy (20-day return reversal — reduced from 40% due to no individual fund PE/PB) |
| trend | 10% | MA20/MA60 crossover + price deviation (minimized — uniformly bullish in current market) |
| momentum | 30% | RSI(14) + MACD(12,26,9) (biggest differentiator) |
| quality | 30% | Fund size + max drawdown |
| sentiment | 15% | NAV volatility contrarian signal |

The engine requires **≥60 NAV records** to score a fund (for MA60 calculation).

**Normalization pipeline:** Two-pass winsorized z-score — collect raw factors across all 13K+ funds → clip at p5/p95 → compute z-scores (clamped to [-3, 3]) → map to [5, 95] range. Old signals for the target date are cleared before regenerating (delete + insert).

**Configurable scoring:** `compute_signal(factor_scores, weights=None, thresholds=None)` in `scorer.py` accepts optional custom weights and signal thresholds. The backtest module uses this to allow parameter experimentation.

## Scheduler

Background APScheduler with two jobs. Each step has try/except error isolation so one failure doesn't cascade.

| Job | Trigger | Steps |
|---|---|---|
| `daily_job` | Daily 20:30 Asia/Shanghai | ① `run_daily_collection()` ② `run_signal_engine()` ③ `run_auto_executor()` |
| `full_sync_job` | Sunday 21:00 Asia/Shanghai | ① `run_rankhandler_fund_sync()` ② `run_daily_collection()` ③ `run_signal_engine()` ④ `run_auto_executor()` |

Estimated runtime: daily ~5 min, weekly ~10 min.

## API Endpoints

All prefixed with `/api`. Auth via JWT Bearer. Register at `/api/docs` (Swagger UI) or `/auth/register`.

### Public (no auth)
- `POST /auth/register` / `/auth/login`

### Auth
- `GET /auth/me` — current user
- `POST /auth/change-password`

### Funds
- `GET /funds` — list (?type=&skip=&limit=&q=&codes=)
- `GET /funds/{code}` / `.../nav` / `.../holdings` / `.../valuations` / `.../signals`

### Signals
- `GET /signals` — list (?level=&action=&skip=&limit=)
- `GET /signals/distribution` — level counts

### Market
- `GET /market/overview` — index quotes + signal distribution + fund count

### Execution List
- `GET/POST /execution-list`, `PUT/DELETE /execution-list/{id}`
- `PUT /execution-list/batch/status` — batch update
- `POST /execution-list/generate-from-signals` — create items from today's signals (only S/A buy items)

### Auto Mode
- `GET/POST /auto/config`, `POST /auto/execute`
- `GET /auto/portfolio` — portfolio + positions + trades
- `GET /auto/reports` — (?period_type=)

### Manual Mode
- `GET /manual/portfolios` — list with positions + trades
- `GET /manual/portfolios/{id}` — single portfolio
- `POST /manual/submit-execution` — submit pending items

### Watchlist
- `GET/POST /watchlist`, `DELETE /watchlist/{id}`

### Admin (trigger background tasks)
- `POST /admin/sync/funds|/sync/funds-rankhandler|/sync/nav|/sync/nav-full` — data sync
- `POST /admin/signals/generate` — run signal engine
- `POST /admin/auto/execute` — trigger auto executor for all users
- `POST /admin/backtest` — run backtest with optional params (body: start_date, end_date, name, params)
- `GET /admin/backtest/results` — list past backtest results (?skip=&limit=)
- `GET /admin/backtest/results/{id}` — get specific result
- `DELETE /admin/backtest/results/{id}` — delete result

### Tools (data reset)
- `POST /tools/reset/auto|/reset/manual|/reset/signals`

## Frontend Routing (React Router)

```
/login /register — auth
/               — Dashboard (market overview, index cards, signal pie chart)
/funds          — Fund list (paginated search table)
/funds/:code    — Fund detail (NAV chart, signal history, holdings)
/signals        — Signal list (level filter)
/signals/:level — Pre-filtered
/auto           — Auto follow config + portfolio
/manual         — Manual execution list (CRUD, batch ops, pagination)
/portfolio      — Manual portfolio (cards with positions/trades)
/watchlist      — Grouped watchlist
/tools          — Admin triggers (sync + data reset)
/settings       — User settings, password change
/backtest       — Date range + results
```

## Commands

All Python scripts must be run from the `backend/` directory (they use `app.` imports). Run `cd backend` first or prefix with `cd backend &&`.

```bash
# Development — start backend (port 8000) + frontend (port 5173) concurrently
npm run dev

# Start backend only (auto-reload on port 8000)
npm run dev:backend

# Start frontend only (port 5173, proxy /api → 8000)
npm run dev:client

# Build frontend for production
npm run build -w client

# Install all dependencies
pip install --break-system-packages -r backend/requirements.txt
npm install

# Run signal engine via CLI (from backend/ directory)
cd backend && python3 -c "import asyncio; from app.services.signal_engine.engine import run_signal_engine; asyncio.run(run_signal_engine())"

# Run rankhandler fund list sync only (fund_code + fund_size, no NAV)
cd backend && python3 -c "import asyncio; from app.services.data_collector.collector import run_rankhandler_fund_sync; asyncio.run(run_rankhandler_fund_sync())"

# Run daily incremental collection (rankhandler batch check + NAV sync)
cd backend && python3 -c "import asyncio; from app.services.data_collector.collector import run_daily_collection; asyncio.run(run_daily_collection())"

# Full NAV sync (all funds, not just outdated)
cd backend && python3 -c "import asyncio; from app.services.data_collector.collector import run_full_nav_sync; asyncio.run(run_full_nav_sync())"

# Batch NAV sync with progress reporting
cd backend && python3 run_batch_sync.py

# Check NAV sync status
cd backend && python3 -c "
import asyncio
from app.database import async_session
from sqlalchemy import select, func, text
from app.models.fund import Fund, FundNav
async def c():
  async with async_session() as db:
    total = await db.execute(select(func.count(FundNav.id)))
    print(f'NAV records: {total.scalar():,}')
    codes = await db.execute(select(FundNav.fund_code).distinct())
    print(f'Funds with NAV: {len([r for r in codes])}')
    r = await db.execute(text('SELECT MAX(date) FROM fund_navs'))
    print(f'Latest NAV date: {r.scalar()}')
asyncio.run(c())
"

# Check signal distribution
cd backend && python3 -c "
import asyncio
from app.database import async_session
from sqlalchemy import select, func, text
from app.models.signal import Signal
from datetime import date
async def c():
  async with async_session() as db:
    r = await db.execute(select(Signal.level, func.count(Signal.id)).where(Signal.date == date.today()).group_by(Signal.level).order_by(Signal.level))
    for l, c in r.all(): print(f'  {l}: {c}')
    r2 = await db.execute(text(f'SELECT MIN(score), MAX(score), AVG(score) FROM signals WHERE date = \"{date.today()}\"'))
    s = r2.one()
    print(f'Score: {s[0]:.0f}-{s[1]:.0f} avg={s[2]:.1f}')
asyncio.run(c())
"

# Testing — there is no automated test framework. Use TEST.md (30 manual API test cases).
# Run the dev servers, then execute the test steps in TEST.md with curl or a REST client.
```

## Access

- Frontend: `http://localhost:5173` (or VM IP :5173)
- Backend API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/api/docs`
- Auth: demo users `test@test.com` / `demo@demo.com` (passwords stored in DB)

## Known Issues & Constraints

- **SQLite concurrency**: No concurrent writes. NAV sync fetches concurrently but writes sequentially per batch. WAL mode (`PRAGMA journal_mode=WAL`) enabled for read concurrency.
- **Signal distribution**: ~96% B (hold) due to NAV-based valuation proxy. Winsorized z-score normalization provides some dispersion (std ~5.6) but the lack of per-fund PE/PB data limits factor differentiation.
- **Fund detail fields sparse**: company, risk_level, manager_id mostly NULL (not available from public APIs).
- **~26,700 total funds** but ~15,000+ are back-end share classes without independent NAV data. Only 13,674 are relevant types (stock/mixed/index).
- **316 recently-established funds** have <60 NAV records and are excluded from signal generation (need more trading days for MA60).
- **No Token auto-refresh**: 401 → redirect to login, no silent refresh.
- **Background tasks** use `asyncio.create_task()`. Note: uvicorn `--reload` kills pending background tasks on file change — wait for code to stabilize before triggering long syncs.

## Key Design Decisions

- **Auto mode** = model validation tool. User sets daily amount + plan_type, system auto-allocates. Cooldown per plan_type (once/day, once/week, once/month).
- **Manual mode** shares the same signal source as auto but allows full user editing before execution.
- **Execution list** → three plan types. `generate-from-signals` only creates buy items (S/A levels) with amounts based on daily_amount. Sell items are not auto-generated.
- **NAV sync** uses **lsjz API with 6-month window** as default (3 requests/fund for first sync, 1 for daily incremental). pingzhongdata full-history used as fallback. MAX_NAV_RECORDS=130.
- **rankhandler batch API** used as primary source for latest NAV + fund_size (4 requests replaces 13K individual requests).
- **Signal engine** processes all funds with NAV data, not just priority funds. Uses **two-pass winsorized z-score normalization** across the full population.
- **Scheduler** has per-step error isolation via `_run_step()`. Daily 20:30 (collection → signals → auto executor), weekly Sun 21:00 (+fund list sync).
- **DB migrations**: Use `ALTER TABLE` manually for existing tables. `create_all` only creates new tables.
- **Scheduler timezone**: APScheduler configured for `Asia/Shanghai` (Beijing time). Daily 20:30, weekly Sun 21:00.
- **WAL mode** enabled via `init_db()` for concurrent reads during sequential writes.
- **Stale docs**: The docstring in `scorer.py` and portions of `PRD-v2.md` still reference old factor weights (40/25/15/10/10) and old NAV coverage metrics (192 funds). The actual weights are set in `FACTOR_WEIGHTS` dict in `scorer.py` (15/10/30/30/15). Current coverage: ~13,674 relevant-type funds with NAV data.
