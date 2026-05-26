"""
Signal API: list signals with fund info, signal distribution.
"""

import json
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from app.database import get_db
from app.models.fund import Fund
from app.models.signal import Signal
from app.services.dependencies import get_current_user
from app.models.user import User
from pydantic import BaseModel


router = APIRouter(prefix="/api/signals", tags=["signals"], dependencies=[Depends(get_current_user)])


class SignalWithFund(BaseModel):
    id: int
    fund_code: str
    fund_name: str
    date: str
    score: float
    level: str
    action: str
    recommendation: dict | None = None

    model_config = {"from_attributes": True}


@router.get("")
async def list_signals(
    level: str | None = None,
    action: str | None = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List signals with fund names, newest first."""
    # Base query
    base_query = select(Signal).join(Fund, Signal.fund_code == Fund.code)
    if level:
        base_query = base_query.where(Signal.level == level)
    if action:
        base_query = base_query.where(Signal.action == action)

    # Get total count
    count_q = select(func.count()).select_from(base_query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Get paginated results
    query = select(Signal, Fund.name).join(Fund, Signal.fund_code == Fund.code)
    if level:
        query = query.where(Signal.level == level)
    if action:
        query = query.where(Signal.action == action)
    query = query.order_by(desc(Signal.date), desc(Signal.score)).offset(skip).limit(limit)

    result = await db.execute(query)
    signals = []
    for row in result.all():
        sig = row[0]
        fund_name = row[1]
        rec = {}
        if sig.recommendation:
            try:
                rec = json.loads(sig.recommendation)
            except (json.JSONDecodeError, TypeError):
                rec = {}
        signals.append({
            "id": sig.id,
            "fund_code": sig.fund_code,
            "fund_name": fund_name,
            "date": str(sig.date),
            "score": sig.score,
            "level": sig.level,
            "action": sig.action,
            "recommendation": rec or None,
        })
    return {"items": signals, "total": total}


@router.get("/distribution")
async def signal_distribution(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get signal level distribution counts."""
    result = await db.execute(
        select(Signal.level, func.count(Signal.id))
        .group_by(Signal.level)
    )
    dist = {row[0]: row[1] for row in result.all()}
    total = sum(dist.values())
    return {
        "distribution": dist,
        "total": total,
        "latest_date": str(
            (await db.execute(select(Signal.date).order_by(desc(Signal.date)).limit(1))).scalar() or ""
        ),
    }
