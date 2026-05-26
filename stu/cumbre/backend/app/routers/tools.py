"""
Tools: data reset endpoints.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db
from app.services.dependencies import get_current_user, get_admin_user
from app.models.user import User


router = APIRouter(prefix="/api/tools", tags=["tools"], dependencies=[Depends(get_current_user)])


@router.post("/reset/auto")
async def reset_auto_data(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Reset all auto-follow data for current user."""
    total = 0

    # Get user's auto portfolio IDs
    result = await db.execute(
        text("SELECT id FROM auto_portfolios WHERE user_id = :uid"), {"uid": user.id}
    )
    pids = [row[0] for row in result.fetchall()]

    if pids:
        for table in ["auto_trades", "auto_positions"]:
            placeholders = ",".join(f":pid_{i}" for i in range(len(pids)))
            params = {f"pid_{i}": pid for i, pid in enumerate(pids)}
            r = await db.execute(
                text(f"DELETE FROM {table} WHERE portfolio_id IN ({placeholders})"), params
            )
            total += r.rowcount

    # Tables with user_id directly
    for table in ["auto_portfolios", "auto_reports", "auto_configs"]:
        r = await db.execute(text(f"DELETE FROM {table} WHERE user_id = :uid"), {"uid": user.id})
        total += r.rowcount

    await db.commit()
    return {"ok": True, "deleted": total}


@router.post("/reset/manual")
async def reset_manual_data(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Reset all manual follow data for current user."""
    total = 0

    # Get user's manual portfolio IDs
    result = await db.execute(
        text("SELECT id FROM manual_portfolios WHERE user_id = :uid"), {"uid": user.id}
    )
    pids = [row[0] for row in result.fetchall()]

    if pids:
        for table in ["manual_trades", "manual_positions"]:
            placeholders = ",".join(f":pid_{i}" for i in range(len(pids)))
            params = {f"pid_{i}": pid for i, pid in enumerate(pids)}
            r = await db.execute(
                text(f"DELETE FROM {table} WHERE portfolio_id IN ({placeholders})"), params
            )
            total += r.rowcount

    # Manual portfolios have user_id
    r = await db.execute(text("DELETE FROM manual_portfolios WHERE user_id = :uid"), {"uid": user.id})
    total += r.rowcount

    # Execution items have user_id
    r = await db.execute(text("DELETE FROM execution_items WHERE user_id = :uid"), {"uid": user.id})
    total += r.rowcount

    await db.commit()
    return {"ok": True, "deleted": total}


@router.post("/reset/signals")
async def reset_signal_data(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_admin_user),
):
    """Delete all signals. Admin only."""
    result = await db.execute(text("DELETE FROM signals"))
    await db.commit()
    return {"ok": True, "deleted": result.rowcount}
