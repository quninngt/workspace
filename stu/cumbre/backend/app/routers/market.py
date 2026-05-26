"""
Market overview API: dashboard data for the frontend.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.database import get_db
from app.models.fund import Fund, IndexQuota
from app.models.signal import Signal
from app.services.dependencies import get_current_user
from app.models.user import User


router = APIRouter(prefix="/api/market", tags=["market"], dependencies=[Depends(get_current_user)])


@router.get("/overview")
async def market_overview(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Market dashboard data: index quotes, signal distribution, fund count."""
    # Index quotas (latest per index) — compatible with both SQLite and PostgreSQL
    # Subquery: get max date per index_code
    subq = (
        select(IndexQuota.index_code, func.max(IndexQuota.date).label("max_date"))
        .group_by(IndexQuota.index_code)
    ).subquery()

    idx_result = await db.execute(
        select(IndexQuota)
        .join(subq, (IndexQuota.index_code == subq.c.index_code) & (IndexQuota.date == subq.c.max_date))
    )
    indices = []
    for row in idx_result.scalars().all():
        indices.append({
            "code": row.index_code,
            "name": row.name,
            "pe": row.pe,
            "pb": row.pb,
            "pe_percentile": row.pe_percentile,
            "pb_percentile": row.pb_percentile,
        })

    # Signal distribution (latest date only)
    latest_signal_date = (await db.execute(
        select(Signal.date).order_by(desc(Signal.date)).limit(1)
    )).scalar()

    if latest_signal_date:
        signal_result = await db.execute(
            select(Signal.level, func.count(Signal.id))
            .where(Signal.date == latest_signal_date)
            .group_by(Signal.level)
        )
    else:
        signal_result = await db.execute(
            select(Signal.level, func.count(Signal.id))
            .group_by(Signal.level)
        )
    signal_distribution = {row[0]: row[1] for row in signal_result.all()}

    # Total fund count
    fund_count = (await db.execute(select(func.count(Fund.code)))).scalar()

    return {
        "indices": indices,
        "signal_distribution": signal_distribution,
        "fund_count": fund_count,
        "latest_signal_date": str(latest_signal_date) if latest_signal_date else None,
    }
