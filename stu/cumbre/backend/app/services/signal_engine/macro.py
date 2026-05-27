"""
Macro signal module: determines market environment based on index PE/PB percentiles.

Signal levels:
- risk_on:  Market is cheap (PE percentile < 30%) → full scores
- neutral:  Market is fair (30%-70%) → mild discount
- risk_off: Market is expensive (PE percentile > 70%) → significant discount

Uses CSI 300 (沪深300) as the primary indicator.
"""

import logging
from datetime import date
from sqlalchemy import select
from app.database import async_session
from app.models.fund import IndexQuota

logger = logging.getLogger(__name__)

# Thresholds for PE percentile (stored as percentage, e.g. 35.0 = 35%)
PE_LOW = 30.0    # Below this → risk_on
PE_HIGH = 70.0   # Above this → risk_off

# Score multipliers for each macro signal
MACRO_MULTIPLIERS = {
    "risk_on": 1.0,
    "neutral": 0.92,
    "risk_off": 0.75,
}

# Primary index codes to check (CSI 300)
PRIMARY_INDEXES = ["000300", "399300"]  # 沪深300 上证/深证


def _determine_signal(pe_pct: float | None, pb_pct: float | None) -> str:
    """Determine macro signal from PE/PB percentiles."""
    # Use PE percentile as primary, PB as confirmation
    if pe_pct is None:
        return "neutral"

    if pe_pct < PE_LOW:
        return "risk_on"
    elif pe_pct > PE_HIGH:
        return "risk_off"
    else:
        return "neutral"


async def get_macro_signal(target_date: date | None = None) -> dict:
    """
    Get the current macro market signal.

    Returns:
        {
            "signal": "risk_on" | "neutral" | "risk_off",
            "multiplier": float,
            "pe_percentile": float | None,
            "pb_percentile": float | None,
            "index_code": str,
            "index_name": str,
            "reasoning": str,
        }
    """
    if target_date is None:
        target_date = date.today()

    async with async_session() as db:
        # Fetch latest IndexQuota for CSI 300
        result = await db.execute(
            select(IndexQuota)
            .where(IndexQuota.index_code.in_(PRIMARY_INDEXES))
            .where(IndexQuota.date <= target_date)
            .order_by(IndexQuota.date.desc())
        )
        rows = result.scalars().all()

    if not rows:
        logger.warning("No IndexQuota data found for macro signal")
        return {
            "signal": "neutral",
            "multiplier": MACRO_MULTIPLIERS["neutral"],
            "pe_percentile": None,
            "pb_percentile": None,
            "index_code": None,
            "index_name": None,
            "reasoning": "无指数估值数据，默认中性",
        }

    # Use the latest record
    latest = rows[0]
    pe_pct = latest.pe_percentile
    pb_pct = latest.pb_percentile
    signal = _determine_signal(pe_pct, pb_pct)
    multiplier = MACRO_MULTIPLIERS[signal]

    # Build reasoning
    pe_str = f"{pe_pct:.1f}%" if pe_pct is not None else "N/A"
    pb_str = f"{pb_pct:.1f}%" if pb_pct is not None else "N/A"

    reasoning_map = {
        "risk_on": f"沪深300 PE百分位 {pe_str}（< {PE_LOW:.0f}%），市场估值偏低，适合积极配置",
        "neutral": f"沪深300 PE百分位 {pe_str}（{PE_LOW:.0f}%-{PE_HIGH:.0f}%），市场估值中性",
        "risk_off": f"沪深300 PE百分位 {pe_str}（> {PE_HIGH:.0f}%），市场估值偏高，建议防守配置",
    }

    return {
        "signal": signal,
        "multiplier": multiplier,
        "pe_percentile": pe_pct,
        "pb_percentile": pb_pct,
        "index_code": latest.index_code,
        "index_name": latest.name,
        "reasoning": reasoning_map[signal],
    }
