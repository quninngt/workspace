"""Grid scan backtester: runs weight configs on TOP 500 funds (memory-safe).

Loads NAV data ONCE for a representative subset of funds (top 500 by NAV count),
reuses across all candidates. Uses a thread pool for computation to avoid
blocking the event loop.
"""

import asyncio
import logging
from datetime import date
from typing import Any

from app.schemas.backtest import BacktestParams
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fund import Fund, FundNav
from app.services.backtesting.backtester import run_backtest_with_data, FACTOR_WEIGHTS

logger = logging.getLogger(__name__)

FACTOR_NAMES = list(FACTOR_WEIGHTS.keys())

# Strategic presets (7 candidates = ~3-5 min total)
CANDIDATES: list[tuple[str, dict[str, float]]] = [
    ("当前默认", FACTOR_WEIGHTS.copy()),
    ("动量+质量主导",   {"valuation": 0.10, "trend": 0.10, "momentum": 0.35, "quality": 0.35, "sentiment": 0.10}),
    ("防御型(质量+估值)", {"valuation": 0.25, "trend": 0.05, "momentum": 0.15, "quality": 0.40, "sentiment": 0.15}),
    ("趋势跟随型",     {"valuation": 0.10, "trend": 0.25, "momentum": 0.25, "quality": 0.25, "sentiment": 0.15}),
    ("估值+情绪主导",   {"valuation": 0.25, "trend": 0.10, "momentum": 0.20, "quality": 0.20, "sentiment": 0.25}),
    ("激进动量",       {"valuation": 0.10, "trend": 0.05, "momentum": 0.50, "quality": 0.20, "sentiment": 0.15}),
    ("等权配置",       {f: 0.20 for f in FACTOR_NAMES}),
]

MAX_GRID_FUNDS = 500  # Use top 500 funds to stay within ~250MB memory


async def _load_sample_data(
    db: AsyncSession,
    start_date: date,
    end_date: date,
) -> tuple[dict[str, list[tuple[date, float]]], dict[str, float | None], dict[date, float], list[date]]:
    """Load NAV data for top N funds only (memory-safe version)."""
    from datetime import timedelta
    lookback = start_date - timedelta(days=365)
    logger.info(f"Loading sample NAV data (top {MAX_GRID_FUNDS} funds): {lookback} ~ {end_date}")

    # 1. Find top N funds by NAV count in the date range
    top_funds = await db.execute(
        select(FundNav.fund_code, func.count(FundNav.id).label("cnt"))
        .where(FundNav.date >= lookback, FundNav.date <= end_date)
        .group_by(FundNav.fund_code)
        .order_by(desc("cnt"))
        .limit(MAX_GRID_FUNDS)
    )
    sample_codes = {r.fund_code for r in top_funds.all()}
    logger.info(f"Selected {len(sample_codes)} representative funds")

    if not sample_codes:
        return {}, {}, [], []

    # 2. Load NAV data for these funds only
    nav_result = await db.execute(
        select(FundNav)
        .where(
            FundNav.fund_code.in_(sample_codes),
            FundNav.date >= lookback,
            FundNav.date <= end_date,
        )
        .order_by(FundNav.fund_code, FundNav.date)
    )
    all_navs = nav_result.scalars().all()

    nav_index: dict[str, list[tuple[date, float]]] = {}
    for row in all_navs:
        nav_index.setdefault(row.fund_code, []).append((row.date, row.nav))

    # 3. Fund metadata
    fund_result = await db.execute(
        select(Fund.code, Fund.fund_size).where(Fund.code.in_(sample_codes))
    )
    fund_sizes: dict[str, float | None] = {r.code: r.fund_size for r in fund_result.all()}

    # 4. CSI 300 benchmark
    idx_result = await db.execute(
        select(FundNav)
        .where(FundNav.fund_code == "000300", FundNav.date >= lookback, FundNav.date <= end_date)
        .order_by(FundNav.date)
    )
    idx_navs: dict[date, float] = {r.date: r.nav for r in idx_result.scalars().all()}

    trading_dates = sorted({row.date for row in all_navs if start_date <= row.date <= end_date})

    total_records = sum(len(v) for v in nav_index.values())
    logger.info(
        f"Sample data loaded: {len(trading_dates)} dates, "
        f"{len(nav_index)} funds, {total_records} NAV records"
    )
    return nav_index, fund_sizes, idx_navs, trading_dates


def _rank_results(results: list[dict]) -> list[dict]:
    scored = []
    for r in results:
        perf = r.get("performance", {})
        sharpe = perf.get("sharpe_ratio", 0) or 0
        ret = perf.get("total_return_pct", 0) or 0
        dd = abs(perf.get("max_drawdown_pct", 0) or 0)
        win = perf.get("win_rate_pct", 0) or 0
        composite = sharpe * 50 + ret * 0.5 - dd * 0.3 + win * 0.2
        scored.append((composite, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    for rank, (score, r) in enumerate(scored, 1):
        r["rank"] = rank
        r["composite_score"] = round(score, 2)
    return [r for _, r in scored]


async def run_grid_scan(
    db: AsyncSession,
    start_date: date,
    end_date: date,
    base_params: BacktestParams | None = None,
) -> dict[str, Any]:
    """Run grid scan on a sample of top funds to find optimal weight configuration."""

    logger.info(f"Grid scan: {len(CANDIDATES)} candidates, {start_date} ~ {end_date}")

    # Load data ONCE (memory-heavy step, but only ~250MB with top 500 funds)
    nav_index, fund_sizes, idx_navs, trading_dates = await _load_sample_data(
        db, start_date, end_date
    )

    if not trading_dates:
        return {"error": "No trading dates in range"}

    if not nav_index:
        return {"error": "No fund data loaded"}

    # Run backtests in thread pool to avoid blocking event loop
    loop = asyncio.get_running_loop()
    results: list[dict] = []

    for label, weights in candidates_normalized():
        params = BacktestParams()
        if base_params:
            params = base_params.model_copy(deep=True)
        params.factor_weights = weights

        try:
            r = await loop.run_in_executor(
                None,
                run_backtest_with_data,
                start_date, end_date, params,
                nav_index, fund_sizes, idx_navs, trading_dates,
            )
            r["label"] = label
            r["weights"] = {k: round(v, 4) for k, v in weights.items()}
            results.append(r)
            perf = r.get("performance", {})
            logger.info(
                f"  [{label}] Sharpe={perf.get('sharpe_ratio', '?')}, "
                f"Return={perf.get('total_return_pct', '?')}%"
            )
        except Exception as e:
            logger.error(f"  [{label}] Failed: {e}")

    ranked = _rank_results(results)
    best = ranked[0] if ranked else None

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "candidates_tried": len(CANDIDATES),
        "successful_runs": len(ranked),
        "ranked_results": ranked,
        "best": best,
        "improvement_vs_default": _calc_improvement(best, ranked),
    }


def candidates_normalized() -> list[tuple[str, dict[str, float]]]:
    """Return candidates with weights normalized to sum 1.0."""
    result = []
    for label, w in CANDIDATES:
        total = sum(w.values())
        if total <= 0:
            continue
        result.append((label, {k: round(v / total, 4) for k, v in w.items()}))
    return result


def _calc_improvement(best: dict | None, ranked: list[dict]) -> dict | None:
    if not best or len(ranked) < 2:
        return None
    default = None
    for r in ranked:
        if r.get("label") == "当前默认":
            default = r
            break
    if not default:
        return None
    bp = best.get("performance", {})
    dp = default.get("performance", {})
    return {
        "sharpe_improvement": round((bp.get("sharpe_ratio", 0) or 0) - (dp.get("sharpe_ratio", 0) or 0), 2),
        "return_improvement_pct": round((bp.get("total_return_pct", 0) or 0) - (dp.get("total_return_pct", 0) or 0), 2),
        "max_dd_reduction_pct": round(abs(dp.get("max_drawdown_pct", 0) or 0) - abs(bp.get("max_drawdown_pct", 0) or 0), 2),
        "best_label": best.get("label", ""),
        "default_label": "当前默认",
    }
