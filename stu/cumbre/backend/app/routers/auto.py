from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.database import get_db
from app.models.auto import AutoConfig, AutoPortfolio, AutoPosition, AutoTrade, AutoReport
from app.models.signal import Signal
from app.models.fund import FundNav
from app.schemas.auto import (
    AutoConfigResponse, AutoPortfolioResponse, AutoPositionResponse,
    AutoTradeResponse, AutoReportResponse, AutoExecuteResponse,
)
from app.services.dependencies import get_current_user
from app.models.user import User


router = APIRouter(prefix="/api/auto", tags=["auto"], dependencies=[Depends(get_current_user)])


async def recalculate_portfolio_market_value(db: AsyncSession, portfolio: AutoPortfolio) -> float:
    """根据最新净值重新计算组合市值"""
    positions_result = await db.execute(
        select(AutoPosition).where(AutoPosition.portfolio_id == portfolio.id)
    )
    positions = positions_result.scalars().all()

    total_market_value = 0.0
    for pos in positions:
        # 获取该基金最新净值
        nav_result = await db.execute(
            select(FundNav)
            .where(FundNav.fund_code == pos.fund_code)
            .order_by(desc(FundNav.date))
            .limit(1)
        )
        latest_nav = nav_result.scalar_one_or_none()
        if latest_nav:
            current_nav = latest_nav.nav or latest_nav.acc_nav
            if current_nav and current_nav > 0:
                total_market_value += pos.shares * current_nav
            else:
                # 如果没有最新净值，使用成本净值估算
                total_market_value += pos.shares * pos.cost_nav
        else:
            total_market_value += pos.shares * pos.cost_nav

    return round(total_market_value, 2)


@router.get("/config", response_model=AutoConfigResponse | None)
async def get_config(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(AutoConfig).where(AutoConfig.user_id == user.id))
    config = result.scalar_one_or_none()
    if config is None:
        return None
    return AutoConfigResponse.model_validate(config)


@router.post("/config", response_model=AutoConfigResponse)
async def save_config(
    total_amount: float | None = None,
    daily_amount: float | None = None,
    plan_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(AutoConfig).where(AutoConfig.user_id == user.id))
    config = result.scalar_one_or_none()
    if config:
        if total_amount is not None:
            config.total_amount = total_amount
        if daily_amount is not None:
            config.daily_amount = daily_amount
        if plan_type is not None:
            config.plan_type = plan_type
    else:
        config = AutoConfig(
            user_id=user.id,
            total_amount=total_amount or 0,
            daily_amount=daily_amount or 0,
            plan_type=plan_type or "daily",
        )
        db.add(config)
    await db.commit()
    await db.refresh(config)
    return AutoConfigResponse.model_validate(config)


@router.post("/execute", response_model=AutoExecuteResponse)
async def execute_auto(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Execute auto-follow: generate trades from today's buy signals.
    Only allowed once per period (daily/weekly/monthly).
    """
    today = date.today()

    # Get config
    result = await db.execute(select(AutoConfig).where(AutoConfig.user_id == user.id))
    config = result.scalar_one_or_none()
    if not config or config.daily_amount <= 0:
        raise HTTPException(status_code=400, detail="请先设置日均投入金额")

    # Cooldown check
    if config.last_executed_at:
        if config.plan_type == "daily" and config.last_executed_at == today:
            raise HTTPException(status_code=400, detail="今日已执行，请明天再试")
        elif config.plan_type == "weekly":
            last_week = config.last_executed_at.isocalendar()[1]
            this_week = today.isocalendar()[1]
            if config.last_executed_at.year == today.year and last_week == this_week:
                raise HTTPException(status_code=400, detail="本周已执行，请下周再试")
        elif config.plan_type == "monthly":
            if config.last_executed_at.year == today.year and config.last_executed_at.month == today.month:
                raise HTTPException(status_code=400, detail="本月已执行，请下月再试")

    # Get today's buy signals
    from sqlalchemy import or_
    signal_q = select(Signal).where(
        Signal.date == today,
        or_(Signal.action == "buy", Signal.level.in_(["A", "S"])),
    )
    signal_result = await db.execute(signal_q)
    signals = signal_result.scalars().all()

    if not signals:
        raise HTTPException(status_code=400, detail="今日无买入信号，无法执行")

    # Get or create portfolio
    pf_result = await db.execute(select(AutoPortfolio).where(AutoPortfolio.user_id == user.id))
    portfolio = pf_result.scalar_one_or_none()
    if not portfolio:
        portfolio = AutoPortfolio(user_id=user.id, cash=0, total_invested=0, market_value=0)
        db.add(portfolio)
        await db.flush()

    # Calculate allocation
    amount_per_fund = max(1, config.daily_amount / len(signals))
    trades_created = 0
    total_amount = 0

    for sig in signals:
        nav_result = await db.execute(
            select(FundNav)
            .where(FundNav.fund_code == sig.fund_code)
            .order_by(desc(FundNav.date))
            .limit(1)
        )
        latest_nav = nav_result.scalar_one_or_none()
        if not latest_nav:
            continue

        nav = latest_nav.nav or latest_nav.acc_nav
        if not nav or nav <= 0:
            continue

        shares = round(amount_per_fund / nav, 2)
        if shares <= 0:
            continue

        trade = AutoTrade(
            portfolio_id=portfolio.id,
            fund_code=sig.fund_code,
            type="buy",
            amount=amount_per_fund,
            shares=shares,
            nav=nav,
            date=today,
            plan_type=config.plan_type,
            signal_id=sig.id,
        )
        db.add(trade)
        trades_created += 1
        total_amount += amount_per_fund

        # Update position
        pos_result = await db.execute(
            select(AutoPosition).where(
                AutoPosition.portfolio_id == portfolio.id,
                AutoPosition.fund_code == sig.fund_code,
            )
        )
        pos = pos_result.scalar_one_or_none()
        if pos:
            total_shares = pos.shares + shares
            total_cost = (pos.shares * pos.cost_nav) + (shares * nav)
            pos.cost_nav = round(total_cost / total_shares, 4) if total_shares > 0 else 0
            pos.shares = round(total_shares, 2)
        else:
            pos = AutoPosition(
                portfolio_id=portfolio.id,
                fund_code=sig.fund_code,
                shares=shares,
                cost_nav=nav,
                allocation_ratio=0,
            )
            db.add(pos)

    if trades_created == 0:
        raise HTTPException(status_code=400, detail="无法获取基金净值，执行失败")

    # Update portfolio
    portfolio.total_invested = (portfolio.total_invested or 0) + total_amount
    portfolio.cash = max(0, (portfolio.cash or 0) - total_amount)

    # Recalculate allocation ratios
    pos_result = await db.execute(
        select(AutoPosition).where(AutoPosition.portfolio_id == portfolio.id)
    )
    all_positions = pos_result.scalars().all()
    total_value = sum(p.shares * p.cost_nav for p in all_positions) or 1
    for p in all_positions:
        p.allocation_ratio = round((p.shares * p.cost_nav) / total_value, 4)

    # 根据最新净值重新计算市值
    portfolio.market_value = await recalculate_portfolio_market_value(db, portfolio)

    # Update last_executed_at
    config.last_executed_at = today

    await db.commit()
    return AutoExecuteResponse(
        ok=True,
        trades_created=trades_created,
        total_amount=total_amount,
        message=f"成功执行 {trades_created} 笔买入交易，总金额 ¥{total_amount:,.0f}",
    )


@router.get("/portfolio", response_model=AutoPortfolioResponse | None)
async def get_portfolio(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(AutoPortfolio).where(AutoPortfolio.user_id == user.id))
    portfolio = result.scalar_one_or_none()
    if portfolio is None:
        return None

    positions_result = await db.execute(
        select(AutoPosition).where(AutoPosition.portfolio_id == portfolio.id)
    )
    trades_result = await db.execute(
        select(AutoTrade).where(AutoTrade.portfolio_id == portfolio.id)
    )

    # 根据最新净值重新计算市值
    new_market_value = await recalculate_portfolio_market_value(db, portfolio)
    if new_market_value != portfolio.market_value:
        portfolio.market_value = new_market_value
        await db.commit()
        await db.refresh(portfolio)

    resp = AutoPortfolioResponse.model_validate(portfolio)
    resp.positions = [AutoPositionResponse.model_validate(p) for p in positions_result.scalars().all()]
    resp.trades = [AutoTradeResponse.model_validate(t) for t in trades_result.scalars().all()]
    return resp


@router.post("/update-market-value")
async def update_market_value(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """手动触发更新组合市值（根据最新净值）"""
    result = await db.execute(select(AutoPortfolio).where(AutoPortfolio.user_id == user.id))
    portfolio = result.scalar_one_or_none()
    if portfolio is None:
        raise HTTPException(status_code=404, detail="组合不存在")

    old_value = portfolio.market_value
    new_value = await recalculate_portfolio_market_value(db, portfolio)
    portfolio.market_value = new_value
    await db.commit()

    return {
        "ok": True,
        "old_market_value": old_value,
        "new_market_value": new_value,
        "change": round(new_value - old_value, 2),
    }


@router.get("/profit-detail")
async def get_profit_detail(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取各基金盈亏明细"""
    result = await db.execute(select(AutoPortfolio).where(AutoPortfolio.user_id == user.id))
    portfolio = result.scalar_one_or_none()
    if portfolio is None:
        raise HTTPException(status_code=404, detail="组合不存在")

    positions_result = await db.execute(
        select(AutoPosition).where(AutoPosition.portfolio_id == portfolio.id)
    )
    positions = positions_result.scalars().all()

    # 计算每个持仓的盈亏
    position_details = []
    total_cost_value = 0
    total_market_value = 0

    for pos in positions:
        # 获取最新净值
        nav_result = await db.execute(
            select(FundNav)
            .where(FundNav.fund_code == pos.fund_code)
            .order_by(desc(FundNav.date))
            .limit(1)
        )
        latest_nav = nav_result.scalar_one_or_none()
        current_nav = (latest_nav.nav or latest_nav.acc_nav) if latest_nav else pos.cost_nav

        cost_value = pos.shares * pos.cost_nav
        market_value = pos.shares * current_nav
        profit_loss = market_value - cost_value
        profit_loss_ratio = (profit_loss / cost_value * 100) if cost_value > 0 else 0

        total_cost_value += cost_value
        total_market_value += market_value

        position_details.append({
            "fund_code": pos.fund_code,
            "shares": pos.shares,
            "cost_nav": pos.cost_nav,
            "current_nav": round(current_nav, 4),
            "cost_value": round(cost_value, 2),
            "market_value": round(market_value, 2),
            "profit_loss": round(profit_loss, 2),
            "profit_loss_ratio": round(profit_loss_ratio, 2),
            "allocation_ratio": pos.allocation_ratio,
        })

    # 按盈亏金额排序
    position_details.sort(key=lambda x: x["profit_loss"], reverse=True)

    total_profit_loss = total_market_value - total_cost_value
    total_profit_loss_ratio = (total_profit_loss / total_cost_value * 100) if total_cost_value > 0 else 0

    return {
        "total_invested": round(portfolio.total_invested, 2),
        "total_cost_value": round(total_cost_value, 2),
        "total_market_value": round(total_market_value, 2),
        "total_profit_loss": round(total_profit_loss, 2),
        "total_profit_loss_ratio": round(total_profit_loss_ratio, 2),
        "positions": position_details
    }


@router.get("/reports", response_model=list[AutoReportResponse])
async def list_reports(
    period_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(AutoReport).where(AutoReport.user_id == user.id)
    if period_type:
        query = query.where(AutoReport.period_type == period_type)
    result = await db.execute(query)
    return [AutoReportResponse.model_validate(r) for r in result.scalars().all()]
