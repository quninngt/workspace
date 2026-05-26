#!/usr/bin/env python3
"""
Quick test script: sync fund list and fetch NAV for a few sample funds.
Run: python3 -m app.services.data_collector.scripts.test_sync
"""

import asyncio
from sqlalchemy import select
from app.database import async_session, init_db
from app.models.fund import Fund
from app.services.data_collector.fund_list import fetch_fund_list
from app.services.data_collector.fund_nav import fetch_nav_history
from app.services.data_collector.fund_holdings import fetch_holdings
from app.services.data_collector.index_quota import fetch_index_quotas
from app.services.data_collector.collector import sync_fund_list, sync_index_quotas, sync_nav, sync_holdings


async def main():
    await init_db()

    async with async_session() as db:
        # 1. Sync fund list
        await sync_fund_list(db)

        # 2. Test with a few sample funds
        sample_codes = ["005827", "110011", "000001"]  # 易方达蓝筹, 易方达中小盘, 华夏成长
        for code in sample_codes:
            n = await sync_nav(code, db, page_size=100)
            print(f"  {code}: {n} NAV records")

            h = await sync_holdings(code, db, top_line=5)
            print(f"  {code}: {h} holdings records")

        # 3. Sync index quotas
        idx = await sync_index_quotas(db)
        print(f"Index quotas: {idx}")

        # 4. Verify
        fund_count = (await db.execute(select(Fund))).scalars().all()
        print(f"\nTotal funds in DB: {len(fund_count)}")

        # Show sample data
        for code in sample_codes:
            result = await db.execute(select(Fund).where(Fund.code == code))
            fund = result.scalar_one_or_none()
            if fund:
                print(f"  {fund.code} {fund.name} [{fund.type}]")


if __name__ == "__main__":
    asyncio.run(main())
