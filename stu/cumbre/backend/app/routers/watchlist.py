from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.watchlist import Watchlist
from app.schemas.watchlist import WatchlistResponse
from app.services.dependencies import get_current_user
from app.models.user import User


router = APIRouter(prefix="/api/watchlist", tags=["watchlist"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[WatchlistResponse])
async def list_watchlist(
    group_name: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Watchlist).where(Watchlist.user_id == user.id)
    if group_name:
        query = query.where(Watchlist.group_name == group_name)
    result = await db.execute(query)
    return [WatchlistResponse.model_validate(w) for w in result.scalars().all()]


@router.post("", response_model=WatchlistResponse)
async def add_watchlist(
    fund_code: str,
    group_name: str = "默认",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    w = Watchlist(user_id=user.id, fund_code=fund_code, group_name=group_name)
    db.add(w)
    await db.commit()
    await db.refresh(w)
    return WatchlistResponse.model_validate(w)


@router.delete("/{item_id}")
async def remove_watchlist(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Watchlist).where(Watchlist.id == item_id, Watchlist.user_id == user.id)
    )
    w = result.scalar_one_or_none()
    if w:
        await db.delete(w)
        await db.commit()
    return {"ok": True}
