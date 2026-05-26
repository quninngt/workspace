"""
Batch NAV sync: efficiently sync NAV data for many funds concurrently.
Uses bulk INSERT OR IGNORE for fast DB writes.

Design:
1. Concurrent HTTP fetch phase (fast, 8 workers)
2. Bulk DB write phase (in-memory filter + parameterized batch INSERT)
"""
import asyncio
import time
from datetime import datetime

from sqlalchemy import select, text
from app.database import async_session, init_db, engine
from app.models.fund import Fund, FundNav
from app.services.data_collector.fund_nav import fetch_nav_history, NavRecord

PRIORITY_TYPES = ["stock", "mixed", "index"]
CONCURRENCY = 8
PAGE_SIZE = 365
BATCH = 2000


async def fetch_records(code: str) -> list[NavRecord] | None:
    try:
        return await fetch_nav_history(code, page_size=PAGE_SIZE)
    except Exception as e:
        print(f"  HTTP error {code}: {e}")
        return None


async def main():
    await init_db()
    start_time = time.time()

    # Phase 1: Build queue + load existing (fund_code, date) pairs
    async with async_session() as db:
        result = await db.execute(
            select(Fund.code, Fund.type).order_by(Fund.code)
        )
        all_funds = result.all()

        existing_codes = {
            row[0] for row in
            (await db.execute(select(FundNav.fund_code).distinct())).all()
        }

    print(f"Total funds: {len(all_funds)} | Already with NAV: {len(existing_codes)}")

    async with async_session() as db:
        rows = await db.execute(text("SELECT fund_code, date FROM fund_navs"))
        existing_pairs = {(r[0], r[1]) for r in rows.all()}
    print(f"Existing NAV records: {len(existing_pairs)}")

    by_type: dict[str, list[str]] = {}
    for code, ftype in all_funds:
        by_type.setdefault(ftype, []).append(code)

    queue = []
    for t in PRIORITY_TYPES:
        for code in by_type.get(t, []):
            if code not in existing_codes:
                queue.append(code)
    for t in by_type:
        if t not in PRIORITY_TYPES:
            for code in by_type[t]:
                if code not in existing_codes:
                    queue.append(code)

    queue = queue[:BATCH]
    print(f"Queue size: {len(queue)}")

    # Phase 2: Concurrent HTTP fetch
    sem = asyncio.Semaphore(CONCURRENCY)

    async def fetcher(code: str) -> tuple[str, list[NavRecord] | None]:
        async with sem:
            records = await fetch_records(code)
            return code, records

    print("Starting concurrent HTTP fetch...")
    fetch_start = time.time()
    results: list[tuple[str, list[NavRecord] | None]] = []

    tasks = [fetcher(code) for code in queue]
    for i, coro in enumerate(asyncio.as_completed(tasks), 1):
        code, records = await coro
        results.append((code, records))
        if i % 100 == 0:
            with_data = sum(1 for _, r in results if r)
            total_recs = sum(len(r) for _, r in results if r)
            elapsed = time.time() - fetch_start
            print(f"  [{i}/{len(tasks)}] fetched | {with_data} have data | {total_recs} records | {i/elapsed:.1f}/s")

    fetch_elapsed = time.time() - fetch_start
    with_data = sum(1 for _, r in results if r)
    print(f"Fetch done ({fetch_elapsed:.1f}s): {with_data} funds have data")

    # Phase 3: Bulk DB write using raw parameterized INSERT
    print("Starting bulk DB write...")
    write_start = time.time()
    total_added = 0
    funds_written = 0

    async with async_session() as db:
        for code, records in results:
            if not records:
                continue
            funds_written += 1

            # Filter to truly new records using in-memory set
            new_batch = []
            for r in records:
                record_date = datetime.strptime(r["date"], "%Y-%m-%d").date()
                if (code, record_date) not in existing_pairs:
                    new_batch.append({
                        "fund_code": code,
                        "date": record_date,
                        "nav": r["nav"],
                        "acc_nav": r["acc_nav"],
                    })
                    existing_pairs.add((code, record_date))

            if new_batch:
                # Parameterized bulk insert
                sql = text(
                    "INSERT INTO fund_navs (fund_code, date, nav, acc_nav) "
                    "VALUES (:fund_code, :date, :nav, :acc_nav)"
                )
                await db.execute(sql, new_batch)
                total_added += len(new_batch)

            if funds_written % 200 == 0:
                await db.commit()

        await db.commit()

        final_count = await db.execute(text("SELECT COUNT(DISTINCT fund_code) FROM fund_navs"))
        final_funds = final_count.scalar()

    write_elapsed = time.time() - write_start
    total_elapsed = time.time() - start_time

    print(f"\n{'='*50}")
    print(f"Batch NAV Sync Complete")
    print(f"{'='*50}")
    print(f"  Fetch:  {fetch_elapsed:.1f}s ({len(queue)} funds)")
    print(f"  Write:  {write_elapsed:.1f}s")
    print(f"  Total:  {total_elapsed:.1f}s")
    print(f"  Funds written:      {funds_written}")
    print(f"  NAV records added:  {total_added}")
    print(f"  Funds with NAV now: {final_funds}")


if __name__ == "__main__":
    asyncio.run(main())
