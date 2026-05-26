from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.database import get_db
from app.models.manual import ExecutionItem, ManualPortfolio, ManualPosition
from app.models.fund import FundNav
from app.schemas.manual import ExecutionItemResponse, ExecutionItemCreate, ExecutionItemUpdate
from app.services.dependencies import get_current_user
from app.models.user import User

VALID_STATUSES = {"pending", "executed", "skipped"}


router = APIRouter(prefix="/api/execution-list", tags=["execution-list"], dependencies=[Depends(get_current_user)])


@router.get("")
async def list_execution_items(
    status: str | None = None,
    plan_type: str | None = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(ExecutionItem).where(ExecutionItem.user_id == user.id)
    if plan_type:
        query = query.where(ExecutionItem.plan_type == plan_type)
    else:
        query = query.where(ExecutionItem.plan_type == "daily")
    if status:
        query = query.where(ExecutionItem.status == status)

    # Count
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Paginated
    query = query.order_by(desc(ExecutionItem.date), ExecutionItem.id).offset(skip).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()

    # 获取用户的手动组合持仓
    portfolio_result = await db.execute(
        select(ManualPortfolio).where(ManualPortfolio.user_id == user.id)
    )
    portfolio = portfolio_result.scalar_one_or_none()

    positions_map = {}
    if portfolio:
        positions_result = await db.execute(
            select(ManualPosition).where(ManualPosition.portfolio_id == portfolio.id)
        )
        for pos in positions_result.scalars().all():
            positions_map[pos.fund_code] = pos

    # 获取所有涉及基金的最新净值
    fund_codes = list(set(item.fund_code for item in items))
    nav_map = {}
    for code in fund_codes:
        nav_result = await db.execute(
            select(FundNav)
            .where(FundNav.fund_code == code)
            .order_by(desc(FundNav.date))
            .limit(1)
        )
        latest_nav = nav_result.scalar_one_or_none()
        if latest_nav:
            nav_map[code] = latest_nav.nav or latest_nav.acc_nav

    # 构建响应，附加持仓和净值信息
    items_with_details = []
    for item in items:
        item_data = ExecutionItemResponse.model_validate(item).model_dump()
        item_data["latest_nav"] = nav_map.get(item.fund_code)
        item_data["current_shares"] = None
        item_data["cost_nav"] = None
        item_data["market_value"] = None
        item_data["profit_loss"] = None
        item_data["profit_loss_ratio"] = None

        if item.fund_code in positions_map:
            pos = positions_map[item.fund_code]
            item_data["current_shares"] = pos.shares
            item_data["cost_nav"] = pos.cost_nav
            latest = nav_map.get(item.fund_code)
            if latest and latest > 0:
                item_data["market_value"] = round(pos.shares * latest, 2)
                cost_value = pos.shares * pos.cost_nav
                if cost_value > 0:
                    item_data["profit_loss"] = round(pos.shares * latest - cost_value, 2)
                    item_data["profit_loss_ratio"] = round((pos.shares * latest - cost_value) / cost_value * 100, 2)

        items_with_details.append(item_data)

    return {"items": items_with_details, "total": total}


@router.post("", response_model=ExecutionItemResponse)
async def create_execution_item(
    body: ExecutionItemCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    today = date.today()
    item = ExecutionItem(
        user_id=user.id,
        plan_type="daily",
        fund_code=body.fund_code,
        action=body.action,
        suggested_amount_min=body.suggested_amount_min,
        suggested_amount_max=body.suggested_amount_max,
        date=today,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return ExecutionItemResponse.model_validate(item)


@router.post("/generate-from-signals")
async def generate_from_signals(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate daily execution items from today's buy signals (S/A levels).
    Consistent with the auto executor — only creates buy items for actionable signals.
    Sets suggested amounts based on signal level and user's auto config daily_amount.
    """
    from app.models.signal import Signal
    from app.models.auto import AutoConfig

    # Only generate buy signals — same as auto executor behavior
    from sqlalchemy import or_
    query = select(Signal).where(
        Signal.date == date.today(),
        or_(Signal.action == "buy", Signal.level.in_(["A", "S"])),
    )
    result = await db.execute(query)
    signals = result.scalars().all()

    if not signals:
        raise HTTPException(status_code=404, detail="今日无买入信号")

    # Sort by score descending, take top 5 for daily execution list
    signals.sort(key=lambda s: s.score, reverse=True)
    signals = signals[:5]

    # Look up user's auto config for suggested amount calculation
    config_result = await db.execute(select(AutoConfig).where(AutoConfig.user_id == user.id))
    config = config_result.scalar_one_or_none()
    daily_amount = config.daily_amount if config and config.daily_amount > 0 else 1000

    # Amount multipliers by signal level
    buy_multipliers = {"S": (2.0, 3.0), "A": (1.0, 1.5)}

    created = 0
    for sig in signals:
        existing = await db.execute(
            select(ExecutionItem).where(
                ExecutionItem.user_id == user.id,
                ExecutionItem.fund_code == sig.fund_code,
                ExecutionItem.plan_type == "daily",
                ExecutionItem.status == "pending",
            )
        )
        if existing.scalar_one_or_none():
            continue

        lo, hi = buy_multipliers.get(sig.level, (1.0, 1.5))
        min_amount = round(daily_amount * lo)
        max_amount = round(daily_amount * hi)

        item = ExecutionItem(
            user_id=user.id,
            plan_type="daily",
            fund_code=sig.fund_code,
            action="buy",
            suggested_amount_min=min_amount,
            suggested_amount_max=max_amount,
            signal_id=sig.id,
            date=date.today(),
            status="pending",
        )
        db.add(item)
        created += 1

    await db.commit()
    return {"created": created, "total_signals": len(signals)}


@router.delete("/{item_id}")
async def delete_execution_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ExecutionItem).where(ExecutionItem.id == item_id, ExecutionItem.user_id == user.id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="执行清单项不存在")
    await db.delete(item)
    await db.commit()
    return {"ok": True}


@router.put("/batch/status")
async def batch_update_status(
    ids: str,
    status: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Batch update execution item status. ids: comma-separated IDs."""
    if status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"无效状态值，允许: {', '.join(VALID_STATUSES)}")
    id_list = [int(i) for i in ids.split(",") if i.strip()]
    if not id_list:
        raise HTTPException(status_code=400, detail="No valid IDs provided")
    result = await db.execute(
        select(ExecutionItem).where(
            ExecutionItem.id.in_(id_list),
            ExecutionItem.user_id == user.id,
        )
    )
    items = result.scalars().all()
    for item in items:
        item.status = status
    await db.commit()
    return {"ok": True, "updated": len(items)}


@router.put("/{item_id}", response_model=ExecutionItemResponse)
async def update_execution_item(
    item_id: int,
    body: ExecutionItemUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ExecutionItem).where(ExecutionItem.id == item_id, ExecutionItem.user_id == user.id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="执行清单项不存在")

    if body.action is not None:
        item.action = body.action
    if body.suggested_amount_min is not None:
        item.suggested_amount_min = body.suggested_amount_min
    if body.suggested_amount_max is not None:
        item.suggested_amount_max = body.suggested_amount_max
    if body.status is not None:
        if body.status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail=f"无效状态值，允许: {', '.join(VALID_STATUSES)}")
        item.status = body.status

    await db.commit()
    await db.refresh(item)
    return ExecutionItemResponse.model_validate(item)
