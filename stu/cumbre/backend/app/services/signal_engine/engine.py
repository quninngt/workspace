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

                # Apply macro multiplier to final score
                adjusted_score = sig["score"] * macro_multiplier
                # Re-derive level from adjusted score
                t = {"S": 80, "A": 65, "B": 40, "C": 25}
                if adjusted_score >= t["S"]:
                    adjusted_level = "S"
                    adjusted_action = "strong_buy"
                elif adjusted_score >= t["A"]:
                    adjusted_level = "A"
                    adjusted_action = "buy"
                elif adjusted_score >= t["B"]:
                    adjusted_level = "B"
                    adjusted_action = "hold"
                elif adjusted_score >= t["C"]:
                    adjusted_level = "C"
                    adjusted_action = "sell"
                else:
                    adjusted_level = "D"
                    adjusted_action = "strong_sell"

                factors_detail = json.dumps({
                    "factors": normalized,
                    "raw_factors": d["raw_factors"],
                    "details": d["details"],
                    "factor_stats": factor_stats,
                    "weights": FACTOR_WEIGHTS,
                    "macro": {
                        "signal": macro["signal"],
                        "multiplier": macro_multiplier,
                        "original_score": sig["score"],
                        "adjusted_score": adjusted_score,
                        "pe_percentile": macro["pe_percentile"],
                        "pb_percentile": macro["pb_percentile"],
                    },
                }, ensure_ascii=False)

                # Generate recommendation
                fi = fund_info.get(d["code"], {})
                recommendation = json.dumps(
                    generate_recommendation(
                        fund_name=fi.get("name", d["code"]),
                        fund_type=fi.get("type"),
                        level=adjusted_level,
                        action=adjusted_action,
                        score=adjusted_score,
                        factor_scores=normalized,
                        factor_details=d["details"],
                    ),
                    ensure_ascii=False,
                )

                record = Signal(
                    fund_code=d["code"],
                    date=target_date,
                    score=adjusted_score,
                    level=adjusted_level,
                    action=adjusted_action,
                    factors_detail=factors_detail,
                    recommendation=recommendation,
                )
                db.add(record)
                signals_created += 1
                if signals_created % 1000 == 0:
                    logger.info(f"  Processed {signals_created}/{len(all_data)}...")
            except Exception as e:
                logger.warning(f"  Error finalizing {d['code']}: {e}")

        await db.commit()
        logger.info(f"Done: {signals_created} signals created for {target_date}")

    logger.info("===== Signal engine complete =====")
