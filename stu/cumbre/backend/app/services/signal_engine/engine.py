"""
Signal engine orchestrator: fetches fund data from database, runs factor scoring,
and stores results as Signal records.

Now integrates macro signal (PE/PB percentile) to adjust scores in different
market environments:
- risk_on:  full scores (×1.0)
- neutral:  mild discount (×0.92)
- risk_off: significant discount (×0.75)
"""

import json
import logging
from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.fund import Fund, FundNav, IndexQuota
from app.models.signal import Signal
from app.services.signal_engine.scorer import compute_signal, FACTOR_WEIGHTS
from app.services.signal_engine.recommendation import generate_recommendation
from app.services.signal_engine.macro import get_macro_signal, MACRO_MULTIPLIERS
from app.services.signal_engine.factors import (
    calculate_trend,
    calculate_momentum,
    calculate_valuation,
    calculate_quality,
    calculate_sentiment,
)

logger = logging.getLogger(__name__)

# Normalization constants for z-score → [0, 100] mapping
Z_CLAMP = 3.0      # z-scores are clamped to [-Z_CLAMP, Z_CLAMP]
Z_SCALE = 18.0     # multiplier: z * Z_SCALE maps to ~[-54, +54]
Z_CENTER = 50.0    # center point: 50 + z * Z_SCALE → [~6, ~94]

# Percentile-based signal level distribution (replaces fixed thresholds)
# Guarantees: S ~5%, A ~15%, B ~40%, C ~25%, D ~15%
LEVEL_PERCENTILES = {
    "S": 0.95,   # top 5%
    "A": 0.80,   # next 15% (80th percentile)
    "B": 0.40,   # middle 40% (40th percentile)
    "C": 0.15,   # next 25% (15th percentile)
    # D: bottom 15%
}
LEVEL_ACTIONS = {"S": "buy", "A": "buy", "B": "hold", "C": "sell", "D": "sell"}


async def _compute_factors(
    db: AsyncSession,
    code: str,
    signal_date: date,
    index_pe_pb: dict[str, tuple[float | None, float | None]] | None = None,
) -> dict | None:
    """
    Compute raw factor scores for a single fund without saving.
    Returns dict of raw factor scores or None if insufficient data.
    """
    result = await db.execute(select(Fund).where(Fund.code == code))
    fund = result.scalar_one_or_none()
    if not fund:
        return None

    nav_result = await db.execute(
        select(FundNav)
        .where(FundNav.fund_code == code)
        .where(FundNav.date <= signal_date)
        .order_by(FundNav.date.asc())
    )
    nav_records = nav_result.scalars().all()

    if len(nav_records) < 60:
        return None

    nav_values = [r.nav for r in nav_records]

    trend_result = calculate_trend(nav_values)
    momentum_result = calculate_momentum(nav_values)

    # #11: Use IndexQuota PE/PB percentile for valuation when available
    pe_pct, pb_pct = None, None
    if index_pe_pb and code in index_pe_pb:
        pe_pct, pb_pct = index_pe_pb[code]
    valuation_result = calculate_valuation(pe_pct, pb_pct, nav_values)

    # #12: Compute max_drawdown_pct from NAV data for quality factor
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
        fund_size=fund.fund_size,
        max_drawdown_pct=max_dd_pct,
        nav_values=nav_values,
    )
    sentiment_result = calculate_sentiment(nav_values)

    # Calculate risk metrics
    from app.services.signal_engine.risk import calculate_risk_metrics
    risk_result = calculate_risk_metrics(nav_values)

    return {
        "code": code,
        "raw_factors": {
            "valuation": valuation_result["score"],
            "trend": trend_result["score"],
            "momentum": momentum_result["score"],
            "quality": quality_result["score"],
            "sentiment": sentiment_result["score"],
        },
        "details": {
            "trend": trend_result["details"],
            "momentum": momentum_result["details"],
            "valuation": valuation_result["details"],
            "quality": quality_result["details"],
            "sentiment": sentiment_result["details"],
            "risk": risk_result,
        },
    }


async def run_signal_engine(target_date: date | None = None):
    """
    Run the signal engine for ALL funds that have NAV data.
    Uses two-pass normalization: first collects raw factor scores across all funds,
    then normalizes them before computing final signals.

    Applies macro signal multiplier based on market PE/PB percentile:
    - risk_on:  ×1.0 (full scores)
    - neutral:  ×0.92 (mild discount)
    - risk_off: ×0.75 (significant discount)
    """
    if target_date is None:
        target_date = date.today()

    logger.info(f"===== Running signal engine for {target_date} =====")

    # Get macro signal for score adjustment
    macro = await get_macro_signal(target_date)
    macro_multiplier = macro["multiplier"]
    logger.info(
        f"Macro signal: {macro['signal']} (multiplier={macro_multiplier}), "
        f"PE percentile={macro['pe_percentile']}, PB percentile={macro['pb_percentile']}"
    )

    async with async_session() as db:
        # Use all funds with NAV data
        result = await db.execute(select(FundNav.fund_code).distinct())
        fund_codes = [row[0] for row in result.all()]

        logger.info(f"Found {len(fund_codes)} funds with NAV data")

        # Pre-load IndexQuota PE/PB percentiles for valuation factor
        # Index funds can use index-level PE/PB; stock/mixed funds use NAV proxy
        idx_result = await db.execute(
            select(IndexQuota.index_code, IndexQuota.pe_percentile, IndexQuota.pb_percentile)
            .where(IndexQuota.date <= target_date)
            .order_by(IndexQuota.index_code, IndexQuota.date.desc())
        )
        # Build a map: index_code → latest (pe_percentile, pb_percentile)
        index_pe_pb: dict[str, tuple[float | None, float | None]] = {}
        seen_codes = set()
        for row in idx_result.all():
            if row[0] not in seen_codes:
                seen_codes.add(row[0])
                index_pe_pb[row[0]] = (row[1], row[2])

        # Phase 1: Collect raw factor scores (no DB writes)
        all_data: list[dict] = []
        for code in fund_codes:
            try:
                factors_data = await _compute_factors(db, code, target_date, index_pe_pb)
                if factors_data:
                    all_data.append(factors_data)
            except Exception as e:
                logger.warning(f"  Error computing factors for {code}: {e}")

        if not all_data:
            logger.warning("No signals could be generated")
            return

        logger.info(f"Collected raw factors for {len(all_data)} funds")

        # Phase 2: Normalize each factor across the fund population
        factor_names = ["valuation", "trend", "momentum", "quality", "sentiment"]
        factor_values: dict[str, list[float]] = {f: [] for f in factor_names}
        for d in all_data:
            for f in factor_names:
                factor_values[f].append(d["raw_factors"][f])

        def _stable_stats(vals):
            sv = sorted(vals)
            n = len(sv)
            if n == 0:
                return {"mean": 50.0, "std": 10.0}
            p5 = sv[int(n * 0.05)]
            p95 = sv[int(n * 0.95)]
            winsorized = [max(p5, min(v, p95)) for v in sv]
            mean = sum(winsorized) / len(winsorized)
            variance = sum((v - mean) ** 2 for v in winsorized) / len(winsorized)
            std = max(variance ** 0.5, 5)
            return {"mean": mean, "std": std}

        factor_stats = {f: _stable_stats(factor_values[f]) for f in factor_names}

        # Clear old signals for target date
        from sqlalchemy import delete as sa_delete
        await db.execute(sa_delete(Signal).where(Signal.date == target_date))

        # Phase 3: Normalize, compute final signals, save
        signals_created = 0
        # Load fund names and types for recommendations
        fund_rows = await db.execute(select(Fund.code, Fund.name, Fund.type))
        fund_info = {r.code: {"name": r.name, "type": r.type} for r in fund_rows}
        # --- 3a: Compute normalized scores for all funds ---
        scored: list[dict] = []
        for d in all_data:
            try:
                normalized = {}
                for f in factor_names:
                    raw = d["raw_factors"][f]
                    s = factor_stats[f]
                    z = (raw - s["mean"]) / s["std"]
                    z = max(-Z_CLAMP, min(Z_CLAMP, z))
                    normalized[f] = Z_CENTER + z * Z_SCALE

                sig = compute_signal(normalized)
                adjusted_score = sig["score"] * macro_multiplier
                scored.append({
                    "code": d["code"],
                    "normalized": normalized,
                    "raw_factors": d["raw_factors"],
                    "details": d["details"],
                    "score": adjusted_score,
                    "original_score": sig["score"],
                })
            except Exception as e:
                logger.warning(f"  Error scoring {d['code']}: {e}")

        if not scored:
            logger.warning("No signals could be scored")
            return

        # --- 3b: Assign levels by percentile rank ---
        scored.sort(key=lambda x: x["score"], reverse=True)
        n = len(scored)

        def _assign_level(rank: int, total: int) -> str:
            """Assign S/A/B/C/D based on percentile rank (0=best)."""
            pct = rank / total  # 0.0 = top, 1.0 = bottom
            if pct < (1 - LEVEL_PERCENTILES["S"]):      # top 5%
                return "S"
            elif pct < (1 - LEVEL_PERCENTILES["A"]):    # next 15%
                return "A"
            elif pct < (1 - LEVEL_PERCENTILES["B"]):    # next 40%
                return "B"
            elif pct < (1 - LEVEL_PERCENTILES["C"]):    # next 25%
                return "C"
            else:                                         # bottom 15%
                return "D"

        level_counts = {"S": 0, "A": 0, "B": 0, "C": 0, "D": 0}

        # --- 3c: Save signals with assigned levels ---
        for rank, item in enumerate(scored):
            try:
                level = _assign_level(rank, n)
                action = LEVEL_ACTIONS[level]
                level_counts[level] += 1

                factors_detail = json.dumps({
                    "factors": item["normalized"],
                    "raw_factors": item["raw_factors"],
                    "details": item["details"],
                    "factor_stats": factor_stats,
                    "weights": FACTOR_WEIGHTS,
                    "macro": {
                        "signal": macro["signal"],
                        "multiplier": macro_multiplier,
                        "original_score": item["original_score"],
                        "adjusted_score": item["score"],
                        "pe_percentile": macro["pe_percentile"],
                        "pb_percentile": macro["pb_percentile"],
                    },
                }, ensure_ascii=False)

                fi = fund_info.get(item["code"], {})
                recommendation = json.dumps(
                    generate_recommendation(
                        fund_name=fi.get("name", item["code"]),
                        fund_type=fi.get("type"),
                        level=level,
                        action=action,
                        score=item["score"],
                        factor_scores=item["normalized"],
                        factor_details=item["details"],
                    ),
                    ensure_ascii=False,
                )

                record = Signal(
                    fund_code=item["code"],
                    date=target_date,
                    score=item["score"],
                    level=level,
                    action=action,
                    factors_detail=factors_detail,
                    recommendation=recommendation,
                )
                db.add(record)
                signals_created += 1
                if signals_created % 2000 == 0:
                    logger.info(f"  Saved {signals_created}/{n}...")
            except Exception as e:
                logger.warning(f"  Error saving signal for {item['code']}: {e}")
        await db.commit()
        logger.info(f"Done: {signals_created} signals for {target_date} | Distribution: {level_counts}")

    logger.info("===== Signal engine complete =====")
