"""
Backtesting service: runs signal engine over historical date ranges and evaluates
trading strategy performance. Uses batch NAV loading for performance.
"""
import json
import logging
import math
import bisect
from datetime import date, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fund import Fund, FundNav
from app.models.signal import Signal
from app.schemas.backtest import BacktestParams
from app.services.signal_engine.scorer import compute_signal, FACTOR_WEIGHTS
from app.services.signal_engine.factors import (
    calculate_trend,
    calculate_momentum,
    calculate_valuation,
    calculate_quality,
    calculate_sentiment,
)

logger = logging.getLogger(__name__)

# Normalization constants (matching engine.py)
Z_CLAMP = 3.0
Z_SCALE = 18.0
Z_CENTER = 50.0


async def run_backtest(
    db: AsyncSession,
    start_date: date,
    end_date: date,
    params: BacktestParams | None = None,
) -> dict:
    """Run historical backtest between start_date and end_date (loads NAV data from DB)."""
    if params is None:
        params = BacktestParams()

    nav_index, fund_sizes, idx_navs, trading_dates = await _load_backtest_data(
        db, start_date, end_date
    )

    if not trading_dates:
        return {"error": "No trading dates in range"}

    return run_backtest_with_data(
        start_date, end_date, params,
        nav_index, fund_sizes, idx_navs, trading_dates,
    )


async def _load_backtest_data(
    db: AsyncSession,
    start_date: date,
    end_date: date,
) -> tuple[dict[str, list[tuple[date, float]]], dict[str, float | None], dict[date, float], list[date]]:
    """Load all NAV data once and return pre-built indices."""
    lookback = start_date - timedelta(days=365)
    logger.info(f"Loading NAV data: {lookback} ~ {end_date}")

    nav_result = await db.execute(
        select(FundNav)
        .where(FundNav.date >= lookback, FundNav.date <= end_date)
        .order_by(FundNav.fund_code, FundNav.date)
    )
    all_navs = nav_result.scalars().all()

    nav_index: dict[str, list[tuple[date, float]]] = {}
    for row in all_navs:
        nav_index.setdefault(row.fund_code, []).append((row.date, row.nav))

    fund_result = await db.execute(select(Fund.code, Fund.fund_size))
    fund_sizes: dict[str, float | None] = {r.code: r.fund_size for r in fund_result.all()}

    idx_result = await db.execute(
        select(FundNav)
        .where(FundNav.fund_code == "000300", FundNav.date >= lookback, FundNav.date <= end_date)
        .order_by(FundNav.date)
    )
    idx_navs: dict[date, float] = {r.date: r.nav for r in idx_result.scalars().all()}

    trading_dates = sorted({row.date for row in all_navs if start_date <= row.date <= end_date})

    logger.info(
        f"Data loaded: {len(trading_dates)} dates, {len(nav_index)} funds, "
        f"{sum(len(v) for v in nav_index.values())} NAV records"
    )

    return nav_index, fund_sizes, idx_navs, trading_dates


def run_backtest_with_data(
    start_date: date,
    end_date: date,
    params: BacktestParams,
    nav_index: dict[str, list[tuple[date, float]]],
    fund_sizes: dict[str, float | None],
    idx_navs: dict[date, float],
    trading_dates: list[date],
) -> dict:
    """Run backtest using pre-loaded NAV data (no DB queries)."""
    lookback = start_date - timedelta(days=365)

    # Pre-compute date index for each fund (for bisect lookups)
    fund_date_index: dict[str, list[date]] = {}
    for code, entries in nav_index.items():
        fund_date_index[code] = [d for d, _ in entries]

    fund_codes = list(nav_index.keys())
    logger.info(
        f"Backtest: {len(trading_dates)} dates, {len(fund_codes)} funds, "
        f"{start_date} ~ {end_date}"
    )

    # --- Phase 2: Simulation ---
    portfolio: dict[str, dict] = {}  # fund_code -> {"shares", "cost_nav"}
    cash = params.initial_capital
    daily_values: list[dict] = []
    signal_stats: dict[str, int] = {"S": 0, "A": 0, "B": 0, "C": 0, "D": 0}
    factor_contributions: dict[str, float] = {k: 0.0 for k in FACTOR_WEIGHTS}
    date_signals_count = 0
    daily_returns: list[float] = []

    active_weights = params.factor_weights or FACTOR_WEIGHTS

    for dt in trading_dates:
        # Compute factors for all funds on this date
        raw_factors_all: list[tuple[str, dict[str, float], float]] = []

        for code in fund_codes:
            entries = nav_index[code]
            date_list = fund_date_index[code]

            # Find slice: all entries up to dt
            idx = bisect.bisect_right(date_list, dt)
            if idx < 60:
                continue

            nav_values = [v for _, v in entries[:idx]]
            latest_nav = nav_values[-1]

            # Compute factors (correct signatures)
            trend_result = calculate_trend(nav_values)
            momentum_result = calculate_momentum(nav_values)
            valuation_result = calculate_valuation(nav_values=nav_values)

            # Quality with max_drawdown_pct
            max_dd_pct = None
            if len(nav_values) > 20:
                peak = nav_values[0]
                max_dd = 0.0
                for v in nav_values:
                    if v > peak:
                        peak = v
                    dd = (peak - v) / peak * 100 if peak > 0 else 0
                    if dd > max_dd:
                        max_dd = dd
                max_dd_pct = max_dd

            quality_result = calculate_quality(
                fund_size=fund_sizes.get(code),
                max_drawdown_pct=max_dd_pct,
                nav_values=nav_values,
            )
            sentiment_result = calculate_sentiment(nav_values=nav_values)

            raw_factors = {
                "valuation": valuation_result["score"],
                "trend": trend_result["score"],
                "momentum": momentum_result["score"],
                "quality": quality_result["score"],
                "sentiment": sentiment_result["score"],
            }

            raw_factors_all.append((code, raw_factors, latest_nav))

        if not raw_factors_all:
            continue

        # Normalize across fund population (optional, matching engine.py)
        if params.normalize_signals and len(raw_factors_all) > 10:
            factor_names = list(FACTOR_WEIGHTS.keys())
            factor_values: dict[str, list[float]] = {f: [] for f in factor_names}
            for _, rf, _ in raw_factors_all:
                for f in factor_names:
                    factor_values[f].append(rf[f])

            factor_stats = {}
            for f in factor_names:
                sv = sorted(factor_values[f])
                n = len(sv)
                p5 = sv[int(n * 0.05)]
                p95 = sv[int(n * 0.95)]
                winsorized = [max(p5, min(v, p95)) for v in sv]
                mean = sum(winsorized) / len(winsorized)
                variance = sum((v - mean) ** 2 for v in winsorized) / len(winsorized)
                std = max(variance ** 0.5, 5)
                factor_stats[f] = {"mean": mean, "std": std}

            signals_for_date = []
            for code, rf, nav in raw_factors_all:
                normalized = {}
                for f in factor_names:
                    s = factor_stats[f]
                    z = (rf[f] - s["mean"]) / s["std"]
                    z = max(-Z_CLAMP, min(Z_CLAMP, z))
                    normalized[f] = Z_CENTER + z * Z_SCALE

                sig = compute_signal(normalized, weights=active_weights, thresholds=params.signal_thresholds)
                signal_stats[sig["level"]] = signal_stats.get(sig["level"], 0) + 1

                strongest = max(rf, key=rf.get)
                factor_contributions[strongest] += 1

                signals_for_date.append((code, sig, nav))
        else:
            signals_for_date = []
            for code, rf, nav in raw_factors_all:
                sig = compute_signal(rf, weights=active_weights, thresholds=params.signal_thresholds)
                signal_stats[sig["level"]] = signal_stats.get(sig["level"], 0) + 1

                strongest = max(rf, key=rf.get)
                factor_contributions[strongest] += 1

                signals_for_date.append((code, sig, nav))

        date_signals_count += len(signals_for_date)

        # --- Execute trading ---
        prev_value = cash + sum(
            p["shares"] * p.get("current_nav", p["cost_nav"]) for p in portfolio.values()
        )

        # Trading cost tracking
        daily_buy_cost = 0.0
        daily_sell_cost = 0.0

        # Sell first (frees cash)
        for code, signal, latest_nav in signals_for_date:
            if signal["action"] == "sell" and code in portfolio:
                ratio = params.sell_ratios.get(signal["level"], 0.25)
                pos = portfolio[code]
                sell_shares = pos["shares"] * ratio
                sell_amount = sell_shares * latest_nav
                
                # Calculate redemption fee based on holding period
                buy_date = pos.get("buy_date", dt)
                holding_days = (dt - buy_date).days
                if holding_days < 7:
                    redemption_fee = params.redemption_fee_short
                elif holding_days <= 365:
                    redemption_fee = params.redemption_fee_medium
                else:
                    redemption_fee = params.redemption_fee_long
                
                # Apply slippage and redemption fee
                cost = sell_amount * (params.slippage + redemption_fee)
                net_sell_amount = sell_amount - cost
                daily_sell_cost += cost
                
                pos["shares"] -= sell_shares
                if pos["shares"] <= 0:
                    del portfolio[code]
                cash += net_sell_amount

        # Buy: sort by score, take top N, exclude already-held funds
        buy_signals = [
            (code, signal, nav) for code, signal, nav in signals_for_date
            if signal["action"] == "buy" and signal["level"] in params.buy_weights and code not in portfolio
        ]
        buy_signals.sort(key=lambda x: x[1]["score"], reverse=True)
        buy_signals = buy_signals[:params.max_daily_buys]

        if buy_signals:
            total_weight = sum(params.buy_weights.get(s["level"], 1.0) for _, s, _ in buy_signals)
            total_value = cash + sum(
                p["shares"] * p.get("current_nav", p["cost_nav"]) for p in portfolio.values()
            )
            max_per_fund = total_value * params.max_single_fund_ratio

            if total_weight > 0 and cash > 0:
                cash_per_weight = cash / total_weight
                for code, signal, nav in buy_signals:
                    weight = params.buy_weights.get(signal["level"], 1.0)
                    buy_amount = cash_per_weight * weight
                    if buy_amount <= 0 or nav <= 0:
                        continue
                    
                    # Apply subscription fee and slippage
                    cost = buy_amount * (params.subscription_fee + params.slippage)
                    net_buy_amount = buy_amount - cost
                    daily_buy_cost += cost
                    
                    shares = net_buy_amount / nav
                    portfolio[code] = {"shares": shares, "cost_nav": nav, "current_nav": nav, "buy_date": dt}
                    cash -= buy_amount

        # Update current_nav for all positions
        for code, signal, nav in signals_for_date:
            if code in portfolio:
                portfolio[code]["current_nav"] = nav

        # Calculate daily portfolio value
        portfolio_value = cash
        for pos in portfolio.values():
            portfolio_value += pos["shares"] * pos.get("current_nav", pos["cost_nav"])

        daily_values.append({
            "date": dt.isoformat(),
            "portfolio_value": round(portfolio_value, 2),
            "cash": round(cash, 2),
            "positions": len(portfolio),
            "signals": len(signals_for_date),
            "buy_cost": round(daily_buy_cost, 2),
            "sell_cost": round(daily_sell_cost, 2),
        })

        # Daily return
        if prev_value > 0:
            daily_returns.append((portfolio_value - prev_value) / prev_value)

        if len(daily_values) % 30 == 0:
            logger.info(f"  Processed {len(daily_values)}/{len(trading_dates)} days...")

    # --- Phase 3: Metrics ---
    start_value = params.initial_capital
    end_value = daily_values[-1]["portfolio_value"] if daily_values else start_value
    total_return = (end_value - start_value) / start_value * 100

    # Max drawdown
    peak = start_value
    max_drawdown = 0
    for dv in daily_values:
        val = dv["portfolio_value"]
        if val > peak:
            peak = val
        dd = (peak - val) / peak * 100
        if dd > max_drawdown:
            max_drawdown = dd

    # Sharpe ratio (annualized, risk-free = 2%)
    if daily_returns:
        mean_ret = sum(daily_returns) / len(daily_returns)
        std_ret = (sum((r - mean_ret) ** 2 for r in daily_returns) / len(daily_returns)) ** 0.5
        sharpe = ((mean_ret - 0.02 / 252) / std_ret * math.sqrt(252)) if std_ret > 0 else 0
    else:
        sharpe = 0

    # Win rate
    win_rate = sum(1 for r in daily_returns if r > 0) / len(daily_returns) * 100 if daily_returns else 0

    # Annualized return
    n_years = len(trading_dates) / 252
    annualized_return = ((end_value / start_value) ** (1 / n_years) - 1) * 100 if n_years > 0 else 0

    # Monthly returns
    monthly_returns = _calc_monthly_returns(daily_values, start_value)

    # Benchmark
    benchmark_return = _calc_benchmark_return(start_date, end_date, idx_navs)

    # Excess return and information ratio
    excess_return = total_return - benchmark_return
    
    # Tracking error (annualized std of excess daily returns)
    benchmark_daily_returns = _calc_benchmark_daily_returns(start_date, trading_dates, idx_navs)
    if daily_returns and benchmark_daily_returns and len(daily_returns) == len(benchmark_daily_returns):
        excess_daily = [r - b for r, b in zip(daily_returns, benchmark_daily_returns)]
        mean_excess = sum(excess_daily) / len(excess_daily)
        tracking_error = (sum((r - mean_excess) ** 2 for r in excess_daily) / len(excess_daily)) ** 0.5 * math.sqrt(252)
        info_ratio = (excess_return / 100) / tracking_error if tracking_error > 0 else 0
    else:
        tracking_error = 0
        info_ratio = 0

    # Profit/loss ratio
    profits = [r for r in daily_returns if r > 0]
    losses = [abs(r) for r in daily_returns if r < 0]
    avg_profit = sum(profits) / len(profits) if profits else 0
    avg_loss = sum(losses) / len(losses) if losses else 0
    profit_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else 0

    # Total trading costs
    total_buy_cost = sum(dv.get("buy_cost", 0) for dv in daily_values)
    total_sell_cost = sum(dv.get("sell_cost", 0) for dv in daily_values)
    total_trading_cost = total_buy_cost + total_sell_cost

    logger.info(
        f"Backtest complete: {len(trading_dates)} days, "
        f"return={total_return:.2f}%, benchmark={benchmark_return:.2f}%, "
        f"excess={excess_return:.2f}%, max_dd={max_drawdown:.2f}%, sharpe={sharpe:.2f}, "
        f"trading_cost={total_trading_cost:.2f}"
    )

    return {
        "summary": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "trading_days": len(trading_dates),
            "funds_scored": len(fund_codes),
            "total_signals_generated": date_signals_count,
        },
        "performance": {
            "total_return_pct": round(total_return, 2),
            "benchmark_return_pct": round(benchmark_return, 2),
            "excess_return_pct": round(excess_return, 2),
            "max_drawdown_pct": round(max_drawdown, 2),
            "final_value": round(end_value, 2),
            "sharpe_ratio": round(sharpe, 2),
            "information_ratio": round(info_ratio, 2),
            "win_rate_pct": round(win_rate, 1),
            "profit_loss_ratio": round(profit_loss_ratio, 2),
            "annualized_return_pct": round(annualized_return, 2),
            "total_trading_cost": round(total_trading_cost, 2),
            "buy_cost": round(total_buy_cost, 2),
            "sell_cost": round(total_sell_cost, 2),
        },
        "signal_distribution": {k: v for k, v in sorted(signal_stats.items())},
        "factor_contributions": {
            k: round(v / max(sum(factor_contributions.values()), 1) * 100, 1)
            for k, v in sorted(factor_contributions.items())
        },
        "monthly_returns": monthly_returns,
        "daily_values": daily_values,
        "params_used": params.model_dump(),
    }


def _calc_monthly_returns(
    daily_values: list[dict], start_value: float
) -> list[dict]:
    """Calculate monthly return percentages."""
    monthly: dict[str, list[float]] = {}
    for dv in daily_values:
        month_key = dv["date"][:7]
        if month_key not in monthly:
            monthly[month_key] = []
        monthly[month_key].append(dv["portfolio_value"])

    result = []
    prev_val = start_value
    for month_key in sorted(monthly):
        vals = monthly[month_key]
        month_end = vals[-1]
        ret = (month_end - prev_val) / prev_val * 100
        result.append({"month": month_key, "return_pct": round(ret, 2)})
        prev_val = month_end
    return result


def _calc_benchmark_return(
    start_date: date,
    end_date: date,
    idx_navs: dict[date, float],
) -> float:
    """Calculate buy-and-hold return for CSI 300 index."""
    dates = sorted(d for d in idx_navs if start_date <= d <= end_date)
    if len(dates) < 2:
        return 0.0
    start_nav = idx_navs[dates[0]]
    end_nav = idx_navs[dates[-1]]
    if start_nav == 0:
        return 0.0
    return (end_nav - start_nav) / start_nav * 100


def _calc_benchmark_daily_returns(
    start_date: date,
    trading_dates: list[date],
    idx_navs: dict[date, float],
) -> list[float]:
    """Calculate daily returns for CSI 300 benchmark."""
    returns = []
    sorted_dates = sorted(d for d in idx_navs if d >= start_date)
    
    for i in range(1, len(trading_dates)):
        dt = trading_dates[i]
        prev_dt = trading_dates[i - 1]
        
        # Find closest available dates in benchmark
        curr_nav = idx_navs.get(dt)
        prev_nav = idx_navs.get(prev_dt)
        
        if curr_nav and prev_nav and prev_nav > 0:
            returns.append(curr_nav / prev_nav - 1)
        else:
            returns.append(0.0)
    
    return returns
