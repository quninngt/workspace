"""
Setup script: clears existing NAV/signal/holding/valuation data,
marks the top 500 funds (by AUM) as priority, and deletes non-priority,
non-relevant-type funds for a clean working set.

Usage: cd backend && python3 scripts/setup_top500.py
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import init_db, async_session
from app.models.fund import Fund, FundNav, FundHolding, FundValuation
from app.models.signal import Signal
from app.models.auto import AutoConfig, AutoPortfolio, AutoPosition, AutoTrade, AutoReport
from app.models.manual import ExecutionItem, ManualPortfolio, ManualPosition, ManualTrade
from sqlalchemy import delete, select

RELEVANT_TYPES = ("stock", "mixed", "index")


async def run():
    await init_db()

    # Load top 500 fund codes
    top500_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "top500_funds.json")
    with open(top500_path) as f:
        top500 = json.load(f)

    top_codes = {f["code"] for f in top500}
    print(f"Loaded {len(top_codes)} top fund codes")

    async with async_session() as db:
        # Step 1: Clear heavy data tables
        print("\n--- Clearing existing data ---")
        for model, name in [
            (FundNav, "NAV records"),
            (Signal, "signals"),
            (FundHolding, "holdings"),
            (FundValuation, "valuations"),
            (ExecutionItem, "execution items"),
            (AutoConfig, "auto configs"),
            (AutoPortfolio, "auto portfolios"),
            (AutoPosition, "auto positions"),
            (AutoTrade, "auto trades"),
            (AutoReport, "auto reports"),
            (ManualPortfolio, "manual portfolios"),
            (ManualPosition, "manual positions"),
            (ManualTrade, "manual trades"),
        ]:
            result = await db.execute(delete(model))
            print(f"  Cleared {name}")

        await db.commit()
        print("  All data cleared")

        # Step 2: Mark top 500 funds as priority
        print("\n--- Marking priority funds ---")
        result = await db.execute(select(Fund))
        all_funds = result.scalars().all()
        print(f"  Total funds in DB: {len(all_funds)}")

        priority_count = 0
        for fund in all_funds:
            if fund.code in top_codes:
                fund.is_priority = 1
                priority_count += 1

        await db.commit()
        print(f"  Marked {priority_count} funds as priority")

        # Step 3: Delete funds that are NOT priority AND NOT relevant types
        # Keep priority funds + non-relevant-type funds (for reference)
        print("\n--- Cleaning up non-priority funds ---")
        result = await db.execute(
            delete(Fund).where(
                Fund.is_priority == 0,
                Fund.type.in_(RELEVANT_TYPES),
            )
        )
        delete_count = result.rowcount
        await db.commit()
        print(f"  Deleted {delete_count} non-priority, relevant-type funds")

        # Step 4: Final count
        result = await db.execute(
            select(Fund).where(Fund.is_priority == 1)
        )
        priority_funds = result.scalars().all()
        result = await db.execute(select(Fund))
        all_remaining = result.scalars().all()
        print(f"\n  Priority funds: {len(priority_funds)}")
        print(f"  Total funds remaining: {len(all_remaining)}")

    print("\n===== Setup complete =====")
    print("Next steps:")
    print("  1. Run NAV sync: python3 -c \"import asyncio; from app.services.data_collector.collector import sync_priority_funds; asyncio.run(sync_priority_funds())\"")
    print("  2. Run signal engine: python3 -c \"import asyncio; from app.services.signal_engine.engine import run_signal_engine; asyncio.run(run_signal_engine())\"")


if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
