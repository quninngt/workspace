"""
Admin/management endpoints: manually trigger data collection and signal generation.
"""

import json as _json
from fastapi import APIRouter, Depends
from app.services.dependencies import get_admin_user
from app.models.user import User
from app.schemas.backtest import BacktestRequest
import asyncio


router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/sync/funds")
async def trigger_fund_sync(user: User = Depends(get_admin_user)):
    """Manually trigger fund list sync (legacy: fundcode_search.js)."""
    asyncio.create_task(_run_fund_sync())
    return {"message": "Fund sync started in background"}


@router.post("/sync/funds-rankhandler")
async def trigger_fund_sync_rankhandler(user: User = Depends(get_admin_user)):
    """Sync fund list + fund_size from rankhandler batch API (4 requests)."""
    asyncio.create_task(_run_rankhandler_fund_sync())
    return {"message": "Rankhandler fund sync started in background"}


@router.post("/sync/nav")
async def trigger_nav_sync(user: User = Depends(get_admin_user)):
    """Daily incremental NAV sync — uses rankhandler for batch latest-NAV check."""
    asyncio.create_task(_run_nav_sync())
    return {"message": "NAV sync started in background (rankhandler batch mode)"}


@router.post("/sync/nav-full")
async def trigger_full_nav_sync(user: User = Depends(get_admin_user)):
    """Manually trigger FULL NAV sync — syncs fund list from rankhandler, then fetches all NAV history."""
    asyncio.create_task(_run_full_nav_sync())
    return {"message": "Full NAV sync started in background (rankhandler fund list + pingzhong NAV)"}


@router.post("/signals/generate")
async def trigger_signal_gen(user: User = Depends(get_admin_user)):
    """Manually trigger signal generation."""
    asyncio.create_task(_run_signal_gen())
    return {"message": "Signal generation started in background"}


async def _run_fund_sync():
    from app.database import init_db, async_session
    from app.services.data_collector.collector import sync_fund_list
    await init_db()
    async with async_session() as db:
        await sync_fund_list(db)


async def _run_rankhandler_fund_sync():
    from app.database import init_db
    from app.services.data_collector.collector import run_rankhandler_fund_sync
    await init_db()
    await run_rankhandler_fund_sync()


async def _run_nav_sync():
    from app.database import init_db, async_session
    from app.services.data_collector.collector import run_daily_collection
    await init_db()
    await run_daily_collection()


async def _run_full_nav_sync():
    from app.database import init_db
    from app.services.data_collector.collector import run_full_nav_sync as full_sync
    await init_db()
    await full_sync()


async def _run_signal_gen():
    from app.database import init_db
    from app.services.signal_engine.engine import run_signal_engine
    from datetime import date
    await init_db()
    await run_signal_engine(target_date=date.today())


@router.post("/auto/execute")
async def trigger_auto_execute(user: User = Depends(get_admin_user)):
    """Manually trigger auto execution for all users with active configs."""
    asyncio.create_task(_run_auto_execute())
    return {"message": "Auto execution started in background"}


async def _run_auto_execute():
    from app.database import init_db, async_session
    from app.services.auto_executor import run_auto_executor
    from datetime import date
    await init_db()
    async with async_session() as db:
        result = await run_auto_executor(db, target_date=date.today())
    logger = __import__("logging").getLogger(__name__)
    logger.info(f"Manual auto execute result: {result}")


@router.post("/backtest")
async def trigger_backtest(
    request: BacktestRequest,
    user: User = Depends(get_admin_user),
):
    """Run backtest with optional parameters."""
    asyncio.create_task(_run_backtest(request))
    return {"message": f"Backtest started: {request.start_date} ~ {request.end_date}"}


async def _run_backtest(request):
    from app.database import init_db, async_session
    from app.services.backtesting.backtester import run_backtest
    from app.models.backtest import BacktestResult

    await init_db()
    async with async_session() as db:
        result = await run_backtest(db, request.start_date, request.end_date, request.params)

        record = BacktestResult(
            name=request.name or f"{request.start_date}~{request.end_date}",
            start_date=request.start_date,
            end_date=request.end_date,
            params=_json.dumps(request.params.model_dump() if request.params else {}, ensure_ascii=False),
            performance=_json.dumps(result["performance"], ensure_ascii=False),
            signal_distribution=_json.dumps(result["signal_distribution"], ensure_ascii=False),
            factor_contributions=_json.dumps(result["factor_contributions"], ensure_ascii=False),
            monthly_returns=_json.dumps(result["monthly_returns"], ensure_ascii=False),
            daily_values=_json.dumps(result["daily_values"], ensure_ascii=False, default=str),
            summary=_json.dumps(result["summary"], ensure_ascii=False),
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)

    _logger = __import__("logging").getLogger(__name__)
    _logger.info(f"Backtest complete: {result['performance']}")


@router.get("/backtest/results")
async def list_backtest_results(
    skip: int = 0,
    limit: int = 20,
    user: User = Depends(get_admin_user),
):
    """List past backtest results, newest first."""
    from app.database import async_session
    from app.models.backtest import BacktestResult
    from sqlalchemy import select, func, desc

    async with async_session() as db:
        count_q = select(func.count(BacktestResult.id))
        total = (await db.execute(count_q)).scalar() or 0

        result = await db.execute(
            select(BacktestResult)
            .order_by(desc(BacktestResult.created_at))
            .offset(skip)
            .limit(limit)
        )
        items = []
        for row in result.scalars().all():
            perf = _json.loads(row.performance) if row.performance else {}
            items.append({
                "id": row.id,
                "name": row.name,
                "start_date": str(row.start_date),
                "end_date": str(row.end_date),
                "performance": perf,
                "created_at": str(row.created_at) if row.created_at else None,
            })

    return {"items": items, "total": total}


@router.get("/backtest/results/{result_id}")
async def get_backtest_result_detail(
    result_id: int,
    user: User = Depends(get_admin_user),
):
    """Get a specific backtest result by ID."""
    from app.database import async_session
    from app.models.backtest import BacktestResult
    from sqlalchemy import select

    async with async_session() as db:
        result = await db.execute(
            select(BacktestResult).where(BacktestResult.id == result_id)
        )
        row = result.scalar_one_or_none()
        if not row:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Backtest result not found")

        return {
            "id": row.id,
            "name": row.name,
            "start_date": str(row.start_date),
            "end_date": str(row.end_date),
            "params": _json.loads(row.params) if row.params else None,
            "performance": _json.loads(row.performance) if row.performance else None,
            "signal_distribution": _json.loads(row.signal_distribution) if row.signal_distribution else None,
            "factor_contributions": _json.loads(row.factor_contributions) if row.factor_contributions else None,
            "monthly_returns": _json.loads(row.monthly_returns) if row.monthly_returns else None,
            "daily_values": _json.loads(row.daily_values) if row.daily_values else None,
            "summary": _json.loads(row.summary) if row.summary else None,
            "created_at": str(row.created_at) if row.created_at else None,
        }


@router.delete("/backtest/results/{result_id}")
async def delete_backtest_result(
    result_id: int,
    user: User = Depends(get_admin_user),
):
    """Delete a backtest result."""
    from app.database import async_session
    from app.models.backtest import BacktestResult
    from sqlalchemy import select

    async with async_session() as db:
        result = await db.execute(
            select(BacktestResult).where(BacktestResult.id == result_id)
        )
        row = result.scalar_one_or_none()
        if not row:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Backtest result not found")
        await db.delete(row)
        await db.commit()

    return {"ok": True}
