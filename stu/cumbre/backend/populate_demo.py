"""
Populate demo data: sync NAV for a batch of funds, then run signal engine.
"""
import asyncio
import sys
sys.path.insert(0, '.')

from app.database import async_session, init_db
from app.models.fund import Fund
from app.services.data_collector.collector import sync_nav, sync_index_quotas
from app.services.signal_engine.engine import run_signal_engine
from datetime import date
from sqlalchemy import select

BATCH_SIZE = 200  # number of funds to process

async def main():
    await init_db()
    async with async_session() as db:
        # Get funds that have no NAV data yet, prioritize stock/mixed/index
        result = await db.execute(
            select(Fund.code, Fund.name, Fund.type)
            .where(Fund.type.in_(['stock', 'mixed', 'index']))
            .order_by(Fund.code)
            .limit(BATCH_SIZE)
        )
        funds = result.all()
        print(f"Will sync NAV for {len(funds)} funds")

        # Sync NAV for each fund
        total = 0
        for i, (code, name, ftype) in enumerate(funds):
            count = await sync_nav(code, db, page_size=365)
            if count:
                total += count
            if (i + 1) % 20 == 0:
                print(f"  Progress: {i+1}/{len(funds)}, NAV records so far: {total}")
                await db.commit()  # ensure progress is saved

        await db.commit()
        print(f"NAV sync done: {total} records for {len(funds)} funds")

        # Sync index quotas
        idx_count = await sync_index_quotas(db)
        print(f"Index quotas: {idx_count}")

    # Run signal engine separately (uses its own session)
    print("Running signal engine...")
    await run_signal_engine(target_date=date.today())
    print("Signal engine done")

if __name__ == '__main__':
    asyncio.run(main())
