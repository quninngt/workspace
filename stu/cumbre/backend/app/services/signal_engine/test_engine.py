#!/usr/bin/env python3
"""
Test the signal engine with sample fund data.
Run: python3 -m app.services.signal_engine.test_engine
"""

import asyncio
from datetime import date, timedelta
from app.database import init_db, async_session
from app.services.data_collector.collector import sync_fund_list, sync_nav, sync_index_quotas
from app.services.signal_engine.engine import score_single_fund
from app.models.signal import Signal
from sqlalchemy import select


async def main():
    await init_db()

    async with async_session() as db:
        # Sync fund list if empty
        from sqlalchemy import func
        cnt = (await db.execute(select(func.count()).select_from(Signal))).scalar()
        print(f"Existing signals: {cnt}")

        # Score a few sample funds
        sample_codes = ["005827", "110011", "000001"]
        today = date.today()

        for code in sample_codes:
            sig = await score_single_fund(db, code, today)
            if sig:
                print(f"\n  {code}: score={sig.score} level={sig.level} action={sig.action}")
                # Show factor breakdown
                import json
                fd = json.loads(sig.factors_detail) if sig.factors_detail else {}
                factors = fd.get("factors", {})
                for f, s in factors.items():
                    print(f"    {f}: {s}")
            else:
                print(f"\n  {code}: insufficient data")

        # Show all signals
        result = await db.execute(select(Signal).order_by(Signal.score.desc()))
        signals = result.scalars().all()
        print(f"\nTotal signals: {len(signals)}")
        for s in signals:
            print(f"  {s.fund_code} [{s.date}]: score={s.score} level={s.level}")


if __name__ == "__main__":
    asyncio.run(main())
