"""
Fund data API: list, detail, NAV history, holdings, signals.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, or_
from app.database import get_db
from app.models.fund import Fund, FundNav, FundHolding, FundValuation
from app.models.signal import Signal
from app.schemas.fund import FundResponse, FundNavResponse, FundHoldingResponse, FundValuationResponse
from app.schemas.signal import SignalResponse
from app.services.dependencies import get_current_user
from app.models.user import User


router = APIRouter(prefix="/api/funds", tags=["funds"], dependencies=[Depends(get_current_user)])


@router.get("")
async def list_funds(
    type: str | None = None,
    codes: str | None = None,  # comma-separated fund codes for batch lookup
    q: str | None = None,  # search by code or name
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Fund)
    count_query = select(func.count(Fund.code))

    if type:
        query = query.where(Fund.type == type)
        count_query = count_query.where(Fund.type == type)
    if codes:
        code_list = [c.strip() for c in codes.split(",") if c.strip()]
        query = query.where(Fund.code.in_(code_list))
        count_query = count_query.where(Fund.code.in_(code_list))
    if q:
        pattern = f"%{q}%"
        query = query.where(or_(Fund.code.like(pattern), Fund.name.like(pattern)))
        count_query = count_query.where(or_(Fund.code.like(pattern), Fund.name.like(pattern)))

    total = (await db.execute(count_query)).scalar() or 0
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    items = [FundResponse.model_validate(f) for f in result.scalars().all()]
    return {"items": items, "total": total}


@router.get("/{code}", response_model=FundResponse)
async def get_fund(
    code: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Fund).where(Fund.code == code))
    fund = result.scalar_one_or_none()
    if not fund:
        raise HTTPException(status_code=404, detail="基金不存在")
    return FundResponse.model_validate(fund)


@router.get("/{code}/nav", response_model=list[FundNavResponse])
async def get_fund_nav(
    code: str,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(FundNav)
        .where(FundNav.fund_code == code)
        .order_by(desc(FundNav.date))
        .limit(limit)
    )
    return [FundNavResponse.model_validate(n) for n in result.scalars().all()]


@router.get("/{code}/holdings", response_model=list[FundHoldingResponse])
async def get_fund_holdings(
    code: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(FundHolding)
        .where(FundHolding.fund_code == code)
        .order_by(desc(FundHolding.date), desc(FundHolding.ratio))
    )
    return [FundHoldingResponse.model_validate(h) for h in result.scalars().all()]


@router.get("/{code}/valuations", response_model=list[FundValuationResponse])
async def get_fund_valuations(
    code: str,
    limit: int = 60,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(FundValuation)
        .where(FundValuation.fund_code == code)
        .order_by(desc(FundValuation.date))
        .limit(limit)
    )
    return [FundValuationResponse.model_validate(v) for v in result.scalars().all()]


@router.get("/{code}/signals", response_model=list[SignalResponse])
async def get_fund_signals(
    code: str,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Signal)
        .where(Signal.fund_code == code)
        .order_by(desc(Signal.date))
        .limit(limit)
    )
    return [SignalResponse.model_validate(s) for s in result.scalars().all()]
