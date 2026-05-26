"""
Auto executor: automatically executes trades based on signals for users with auto mode enabled.
Runs after daily signal generation as part of the scheduler pipeline.
"""
import json
import logging
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.auto import AutoConfig, AutoPortfolio, AutoPosition, AutoTrade
from app.models.signal import Signal
from app.models.fund import FundNav

logger = logging.getLogger(__name__)

# Signal weight mapping for buy allocation
BUY_WEIGHTS = {"S": 2.0, "A": 1.0}
# Sell ratios for sell signals
SELL_RATIOS = {"C": 0.25, "D": 0.50}
# Max single fund allocation ratio
MAX_SINGLE_FUND_RATIO = 0.30
# Max buy trades per day
MAX_DAILY_BUYS = 5


async def run_auto_executor(db: AsyncSession, target_date: date | None = None) -> dict:
    """
    Main entry point: execute auto-trading for all users with active configs.
    Called from scheduler after daily signal generation.
    """
    if target_date is None:
        target_date = date.today()

    # 1. Find all active auto configs
    result = await db.execute(
        select(AutoConfig).where(AutoConfig.status == "active")
    )
    configs = result.scalars().all()

    if not configs:
        logger.info("No active auto configs found, skipping auto execution")
        return {"users_processed": 0, "total_trades": 0, "total_amount": 0.0}

    total_trades = 0
    total_amount = 0.0

    for config in configs:
        trades, amount = await _execute_for_user(db, config, target_date)
        total_trades += trades
        total_amount += amount

    logger.info(
        f"Auto executor complete: {len(configs)} users, "
        f"{total_trades} trades, ¥{total_amount:.2f}"
    )
    return {
        "users_processed": len(configs),
        "total_trades": total_trades,
        "total_amount": total_amount,
    }


async def _execute_for_user(
    db: AsyncSession,
    config: AutoConfig,
    target_date: date,
) -> tuple[int, float]:
    """Execute auto-trading for a single user."""
    trades_created = 0
    total_amount = 0.0

    # 2. Get or create portfolio
    port_result = await db.execute(
        select(AutoPortfolio).where(AutoPortfolio.user_id == config.user_id)
    )
    portfolio = port_result.scalar_one_or_none()
    if not portfolio:
        portfolio = AutoPortfolio(
            user_id=config.user_id,
            cash=0,
            total_invested=0,
            market_value=0,
        )
        db.add(portfolio)
        await db.flush()

    # Add periodic investment amount to cash before executing
    # Calculate based on plan type: daily_amount is the daily target
    if config.plan_type == "weekly":
        periodic_amount = config.daily_amount * 5
    elif config.plan_type == "monthly":
        periodic_amount = config.daily_amount * 22
    else:
        periodic_amount = config.daily_amount
    portfolio.cash += periodic_amount
    logger.info(
        f"User {config.user_id}: added ¥{periodic_amount:.2f} ({config.plan_type}) periodic investment, "
        f"cash now ¥{portfolio.cash:.2f}"
    )

    # 3. Load existing positions
    pos_result = await db.execute(
        select(AutoPosition).where(AutoPosition.portfolio_id == portfolio.id)
    )
    existing_positions = {p.fund_code: p for p in pos_result.scalars().all()}

    # 4. Get today's signals
    signal_result = await db.execute(
        select(Signal).where(Signal.date == target_date)
    )
    signals = signal_result.scalars().all()

    if not signals:
        logger.info(f"No signals for {target_date}, skipping user {config.user_id}")
        return (0, 0.0)

    # 5. Get latest NAV for all relevant fund codes
    fund_codes = list({s.fund_code for s in signals})
    nav_map = await _get_latest_navs(db, fund_codes)

    # 6. Categorize signals
    buy_signals = [s for s in signals if s.level in ("S", "A")]
    sell_signals = [s for s in signals if s.level in ("C", "D")]

    # 7. Process sell signals first (frees up cash)
    for signal in sell_signals:
        pos = existing_positions.get(signal.fund_code)
        if not pos or pos.shares <= 0:
            continue

        nav = nav_map.get(signal.fund_code)
        if not nav or nav <= 0:
            continue

        ratio = SELL_RATIOS.get(signal.level, 0.25)
        sell_shares = pos.shares * ratio
        sell_amount = sell_shares * nav

        db.add(AutoTrade(
            portfolio_id=portfolio.id,
            fund_code=signal.fund_code,
            type="sell",
            amount=sell_amount,
            shares=sell_shares,
            nav=nav,
            date=target_date,
            plan_type="daily",
            signal_id=signal.id,
        ))

        pos.shares -= sell_shares
        portfolio.cash += sell_amount
        trades_created += 1

    # 8. Process buy signals — top N by score only
    if buy_signals:
        buy_signals.sort(key=lambda s: s.score, reverse=True)
        buy_signals = buy_signals[:MAX_DAILY_BUYS]
        available_cash = portfolio.cash
        total_weight = sum(BUY_WEIGHTS.get(s.level, 1.0) for s in buy_signals)

        if total_weight > 0 and available_cash > 0:
            # Calculate total portfolio value for cap
            total_value = portfolio.cash + portfolio.market_value
            max_per_fund = total_value * MAX_SINGLE_FUND_RATIO
            cash_per_weight = available_cash / total_weight

            for signal in buy_signals:
                nav = nav_map.get(signal.fund_code)
                if not nav or nav <= 0:
                    continue

                weight = BUY_WEIGHTS.get(signal.level, 1.0)
                buy_amount = cash_per_weight * weight

                # Cap at max single fund allocation
                pos = existing_positions.get(signal.fund_code)
                current_value = (pos.shares * pos.cost_nav) if pos else 0
                if current_value + buy_amount > max_per_fund:
                    buy_amount = max(0, max_per_fund - current_value)

                if buy_amount <= 0:
                    continue

                shares = buy_amount / nav
                if shares <= 0:
                    continue

                db.add(AutoTrade(
                    portfolio_id=portfolio.id,
                    fund_code=signal.fund_code,
                    type="buy",
                    amount=buy_amount,
                    shares=shares,
                    nav=nav,
                    date=target_date,
                    plan_type="daily",
                    signal_id=signal.id,
                ))

                # Update or create position
                if signal.fund_code in existing_positions:
                    pos = existing_positions[signal.fund_code]
                    total_shares = pos.shares + shares
                    pos.cost_nav = (
                        pos.cost_nav * pos.shares + nav * shares
                    ) / total_shares
                    pos.shares = total_shares
                else:
                    pos = AutoPosition(
                        portfolio_id=portfolio.id,
                        fund_code=signal.fund_code,
                        shares=shares,
                        cost_nav=nav,
                        allocation_ratio=0,
                    )
                    db.add(pos)
                    existing_positions[signal.fund_code] = pos

                portfolio.cash -= buy_amount
                total_amount += buy_amount
                trades_created += 1

    # 9. Update portfolio summary
    portfolio.total_invested += total_amount
    market_value = 0
    for pos in existing_positions.values():
        nav = nav_map.get(pos.fund_code)
        if nav and nav > 0 and pos.shares > 0:
            market_value += pos.shares * nav
    portfolio.market_value = market_value

    # Update allocation ratios based on total portfolio value
    total_value = portfolio.cash + market_value
    if total_value > 0:
        for pos in existing_positions.values():
            nav = nav_map.get(pos.fund_code)
            if nav and nav > 0 and pos.shares > 0:
                pos.allocation_ratio = pos.shares * nav / total_value
            else:
                pos.allocation_ratio = 0

    # 10. Log execution summary
    nav_history = json.loads(portfolio.nav_history) if portfolio.nav_history else []
    nav_history.append({
        "date": target_date.isoformat(),
        "market_value": round(market_value, 2),
        "cash": round(portfolio.cash, 2),
        "total": round(market_value + portfolio.cash, 2),
    })
    portfolio.nav_history = json.dumps(nav_history[-365:])  # Keep last year

    config.last_executed_at = target_date
    await db.commit()

    logger.info(
        f"User {config.user_id}: {trades_created} trades, "
        f"¥{total_amount:.2f}, cash=¥{portfolio.cash:.2f}, "
        f"market_value=¥{portfolio.market_value:.2f}"
    )
    return (trades_created, total_amount)


async def _get_latest_navs(
    db: AsyncSession, fund_codes: list[str]
) -> dict[str, float]:
    """Get the latest NAV for each fund code."""
    nav_map: dict[str, float] = {}
    for code in fund_codes:
        result = await db.execute(
            select(FundNav)
            .where(FundNav.fund_code == code)
            .order_by(FundNav.date.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row:
            nav_map[code] = row.nav
    return nav_map
