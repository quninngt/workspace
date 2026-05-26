"""
Batch NAV sync with progress reporting.
Run from backend/ directory: python3 run_batch_sync.py
"""
import asyncio
import time
import sys
from datetime import datetime

from app.database import async_session
from app.models.fund import Fund, FundNav
from sqlalchemy import select, func


async def main():
    async with async_session() as db:
        r = await db.execute(
            select(Fund.code).where(Fund.type.in_(["stock", "mixed", "index"])).order_by(Fund.code)
        )
        all_codes = [row[0] for row in r.all()]

    total = len(all_codes)
    t_start = time.time()
    print(f"\n{'='*60}")
    print(f"全量 NAV 同步 | {total} 只基金 | {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}\n")

    from app.services.data_collector.collector import sync_nav_batch

    BATCH = 200
    CONCURRENCY = 12
    total_new = 0

    for i in range(0, total, BATCH):
        batch = all_codes[i : i + BATCH]
        batch_num = i // BATCH + 1
        total_batches = (total + BATCH - 1) // BATCH

        t_batch = time.time()
        new_records = await sync_nav_batch(batch, concurrency=CONCURRENCY, label=f"B{batch_num}")
        total_new += new_records

        elapsed = time.time() - t_batch
        total_elapsed = time.time() - t_start
        done = min(i + BATCH, total)
        pct = done / total * 100
        eta = (total_elapsed / done) * (total - done) if done > 0 else 0

        rate = done / total_elapsed if total_elapsed > 0 else 0
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] B{batch_num}/{total_batches} | "
            f"+{new_records:5d}条 | {done:5d}/{total} ({pct:5.1f}%) | "
            f"{elapsed:3.0f}s/{eta:4.0f}s | {rate:.1f}只/s",
            flush=True,
        )

    async with async_session() as db:
        r = await db.execute(select(func.count(FundNav.id)))
        final_records = r.scalar()

    total_elapsed = time.time() - t_start
    print(f"\n{'='*60}")
    print(f"完成! 耗时 {total_elapsed:.0f}s ({total_elapsed/60:.1f}min)")
    print(f"总 NAV 记录: {final_records}")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
