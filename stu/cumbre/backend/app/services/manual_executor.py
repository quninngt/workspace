"""
Manual executor: submits pending daily execution items to create a manual portfolio.
"""
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.manual import ExecutionItem, ManualPortfolio, ManualPosition, ManualTrade
from app.models.fund import FundNav


async def submit_execution(
    db: AsyncSession,
    user_id: int,
) -> dict:
    """
    Submit all pending daily execution items for a user.
    Creates portfolio, positions, and trades.
    """
    # 1. Get pending daily items
    query = select(ExecutionItem).where(
        ExecutionItem.user_id == user_id,
        ExecutionItem.plan_type == "daily",
        ExecutionItem.status == "pending",
    )

    result = await db.execute(query)
    items = result.scalars().all()

    if not items:
        return {"trades_created": 0, "total_amount": 0.0, "portfolio_id": None, "portfolio_name": ""}

    # 2. Get or create portfolio
    port_result = await db.execute(
        select(ManualPortfolio).where(ManualPortfolio.user_id == user_id)
    )
    portfolio = port_result.scalar_one_or_none()

    if not portfolio:
        portfolio = ManualPortfolio(
            user_id=user_id,
            name="默认组合",
            cash=0,
            total_invested=0,
        )
        db.add(portfolio)
        await db.flush()

    # 3. Collect latest NAV for each unique fund code
    fund_codes = list({item.fund_code for item in items if item.action in ("buy", "sell")})
    nav_map: dict[str, float] = {}
    for code in fund_codes:
        nav_result = await db.execute(
            select(FundNav)
            .where(FundNav.fund_code == code)
            .order_by(FundNav.date.desc())
            .limit(1)
        )
        nav_row = nav_result.scalar_one_or_none()
        if nav_row:
            nav_map[code] = nav_row.nav

    # 4. Load existing positions
    pos_result = await db.execute(
        select(ManualPosition).where(ManualPosition.portfolio_id == portfolio.id)
    )
    existing_positions = {p.fund_code: p for p in pos_result.scalars().all()}

    # 5. Process each item
    trades_created = 0
    total_amount = 0.0

    for item in items:
        nav = nav_map.get(item.fund_code)
        amount = ((item.suggested_amount_min or 0) + (item.suggested_amount_max or 0)) / 2
        if amount == 0:
            amount = 1000  # default amount if no suggestion

        if item.action == "buy" and nav and nav > 0:
            shares = amount / nav
            db.add(ManualTrade(
                portfolio_id=portfolio.id,
                fund_code=item.fund_code,
                type="buy",
                amount=amount,
                shares=shares,
                nav=nav,
                date=item.date,
                execution_id=item.id,
            ))
            if item.fund_code in existing_positions:
                pos = existing_positions[item.fund_code]
                total_shares = pos.shares + shares
                pos.cost_nav = (pos.cost_nav * pos.shares + nav * shares) / total_shares
                pos.shares = total_shares
            else:
                pos = ManualPosition(
                    portfolio_id=portfolio.id,
                    fund_code=item.fund_code,
                    shares=shares,
                    cost_nav=nav,
                )
                db.add(pos)
                existing_positions[item.fund_code] = pos

            trades_created += 1
            total_amount += amount

        elif item.action == "sell" and item.fund_code in existing_positions:
            pos = existing_positions[item.fund_code]
            sell_shares = min(pos.shares, amount / nav if nav else pos.shares)
            if nav and nav > 0:
                sell_amount = sell_shares * nav
                db.add(ManualTrade(
                    portfolio_id=portfolio.id,
                    fund_code=item.fund_code,
                    type="sell",
                    amount=sell_amount,
                    shares=sell_shares,
                    nav=nav,
                    date=item.date,
                    execution_id=item.id,
                ))
                pos.shares -= sell_shares
                trades_created += 1
                total_amount += sell_amount

        if item.action == "hold":
            item.status = "skipped"
        elif item.action in ("buy", "sell") and trades_created:
            item.status = "executed"
        else:
            item.status = "skipped"

    # 6. Update portfolio summary
    portfolio.total_invested += total_amount
    today = date.today()

    await db.commit()

    return {
        "trades_created": trades_created,
        "total_amount": total_amount,
        "portfolio_id": portfolio.id,
        "portfolio_name": portfolio.name,
    }
