from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.database import get_db
from app.models.manual import ManualPortfolio, ManualPosition, ManualTrade
from app.models.fund import FundNav
from app.schemas.manual import ManualPortfolioResponse, ManualPositionResponse, ManualTradeResponse, SubmitExecutionResponse
from app.services.dependencies import get_current_user
from app.models.user import User
from app.services.manual_executor import submit_execution


router = APIRouter(prefix="/api/manual", tags=["manual"], dependencies=[Depends(get_current_user)])


@router.get("/portfolios", response_model=list[ManualPortfolioResponse])
async def list_portfolios(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(ManualPortfolio).where(ManualPortfolio.user_id == user.id))
    portfolios = []
    for p in result.scalars().all():
        resp = ManualPortfolioResponse.model_validate(p)
        positions_result = await db.execute(
            select(ManualPosition).where(ManualPosition.portfolio_id == p.id)
        )
        trades_result = await db.execute(
            select(ManualTrade).where(ManualTrade.portfolio_id == p.id)
        )
        resp.positions = [ManualPositionResponse.model_validate(pos) for pos in positions_result.scalars().all()]
        resp.trades = [ManualTradeResponse.model_validate(t) for t in trades_result.scalars().all()]
        portfolios.append(resp)
    return portfolios


@router.get("/portfolios/{portfolio_id}", response_model=ManualPortfolioResponse)
async def get_portfolio(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ManualPortfolio).where(ManualPortfolio.id == portfolio_id, ManualPortfolio.user_id == user.id)
    )
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="组合不存在")

    resp = ManualPortfolioResponse.model_validate(p)
    positions_result = await db.execute(
        select(ManualPosition).where(ManualPosition.portfolio_id == p.id)
    )
    trades_result = await db.execute(
        select(ManualTrade).where(ManualTrade.portfolio_id == p.id)
    )
    resp.positions = [ManualPositionResponse.model_validate(pos) for pos in positions_result.scalars().all()]
    resp.trades = [ManualTradeResponse.model_validate(t) for t in trades_result.scalars().all()]
    return resp


@router.post("/submit-execution", response_model=SubmitExecutionResponse)
async def submit_execution_endpoint(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Submit all pending execution items for this user."""
    result = await submit_execution(db, user.id)
    return result


@router.get("/portfolio-summary")
async def get_portfolio_summary(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取手动组合持仓汇总，包含盈亏信息"""
    # 获取用户的手动组合
    portfolio_result = await db.execute(
        select(ManualPortfolio).where(ManualPortfolio.user_id == user.id)
    )
    portfolio = portfolio_result.scalar_one_or_none()

    if not portfolio:
        return {
            "total_invested": 0,
            "total_market_value": 0,
            "total_profit_loss": 0,
            "total_profit_loss_ratio": 0,
            "positions": []
        }

    # 获取所有持仓
    positions_result = await db.execute(
        select(ManualPosition).where(ManualPosition.portfolio_id == portfolio.id)
    )
    positions = positions_result.scalars().all()

    # 计算每个持仓的盈亏
    position_details = []
    total_market_value = 0
    total_cost_value = 0

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

        total_market_value += market_value
        total_cost_value += cost_value

        position_details.append({
            "fund_code": pos.fund_code,
            "shares": pos.shares,
            "cost_nav": pos.cost_nav,
            "current_nav": round(current_nav, 4),
            "cost_value": round(cost_value, 2),
            "market_value": round(market_value, 2),
            "profit_loss": round(profit_loss, 2),
            "profit_loss_ratio": round(profit_loss_ratio, 2),
        })

    # 按盈亏金额排序
    position_details.sort(key=lambda x: x["profit_loss"], reverse=True)

    total_profit_loss = total_market_value - total_cost_value
    total_profit_loss_ratio = (total_profit_loss / total_cost_value * 100) if total_cost_value > 0 else 0

    return {
        "total_invested": round(portfolio.total_invested, 2),
        "total_market_value": round(total_market_value, 2),
        "total_profit_loss": round(total_profit_loss, 2),
        "total_profit_loss_ratio": round(total_profit_loss_ratio, 2),
        "positions": position_details
    }
