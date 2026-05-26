"""
Orchestrator: coordinates data collection from all sources and stores results in DB.
Optimized with:
  - pingzhongdata for full-history NAV fetch (1 request vs ~19 for lsjz)
  - Incremental sync (only fetch records after last known date)
  - Concurrent batch NAV sync with configurable concurrency
  - Only process relevant fund types (stock, mixed, index)

Concurrency strategy for SQLite:
  Phase 1 — Concurrent HTTP fetches across funds (the bottleneck)
  Phase 2 — Sequential DB writes per batch (SQLite doesn't support concurrent writes)
"""

import json
import asyncio
import logging
import re
import httpx
from datetime import date, datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, text

from app.database import async_session
from app.models.fund import Fund, FundNav, FundHolding, FundValuation, IndexQuota
from app.services.data_collector.fund_list import fetch_fund_list, fetch_fund_detail
from app.services.data_collector.fund_nav import fetch_nav_from_pingzhong, fetch_nav_history
from app.services.data_collector.fund_holdings import fetch_holdings
from app.services.data_collector.index_quota import fetch_index_quotas

logger = logging.getLogger(__name__)

# Only these fund types are relevant for signal generation
RELEVANT_TYPES = ("stock", "mixed", "index")

RANKHANDLER_URL = "https://fund.eastmoney.com/data/rankhandler.aspx"
RANKHANDLER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://fund.eastmoney.com/data/fundranking.html",
}


async def _fetch_rankhandler_page(ft: str, page: int = 1, page_size: int = 5000) -> list[list[str]]:
    """Fetch one page from rankhandler API, sorted by fund_size desc."""
    params = {
        "op": "ph", "dt": "kf", "ft": ft, "rs": "", "gs": "0",
        "sc": "njjgm", "st": "desc",
        "pi": str(page), "pn": str(page_size), "dx": "1",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(RANKHANDLER_URL, params=params, headers=RANKHANDLER_HEADERS)
    text = resp.text.strip().replace("var rankData = ", "", 1).rstrip(";")
    m = re.search(r"datas:\[(.+?)\]\s*,\s*allRecords:(\d+)", text, re.DOTALL)
    if not m:
        return []
    return json.loads("[" + m.group(1) + "]")


FT_MAP = {"gp": "stock", "zs": "index", "hh": "mixed"}


async def fetch_funds_from_rankhandler() -> list[dict]:
    """
    Fetch all relevant funds (stock, index, mixed) with fund_size and latest NAV
    from rankhandler API. Uses 4 requests total (mixed needs 2 pages at pn=5000).
    Returns list of {code, name, type, fund_size_yi, nav_date, nav, acc_nav, establish_date}.
    """
    all_funds = []
    configs = [("gp", 1), ("zs", 1), ("hh", 1), ("hh", 2)]
    for ft, page in configs:
        rows = await _fetch_rankhandler_page(ft, page=page, page_size=5000)
        if not rows:
            continue
        fund_type = FT_MAP[ft]
        for row in rows:
            fields = row.split(",")
            if len(fields) < 19:
                continue
            code = fields[0].strip('"')
            size_str = fields[18].strip()
            fund_size_yi = float(size_str) if size_str and size_str != "-" else None
            est_date = fields[16].strip()
            all_funds.append({
                "code": code,
                "name": fields[1].strip(),
                "type": fund_type,
                "fund_size_yi": fund_size_yi,
                "nav_date": fields[3].strip(),
                "nav": float(fields[4]) if fields[4] else None,
                "acc_nav": float(fields[5]) if fields[5] else None,
                "establish_date": est_date if est_date and est_date != "-" else None,
            })
    return all_funds


async def sync_fund_list_from_rankhandler(db: AsyncSession) -> int:
    """
    Sync fund list and fund_size from rankhandler batch API.
    Upserts Fund records — updates fund_size, name, type for existing funds.
    Returns count of upserted records.
    """
    funds = await fetch_funds_from_rankhandler()
    if not funds:
        logger.warning("rankhandler returned no data")
        return 0

    # Batch query: load all existing fund codes in one SELECT
    result = await db.execute(select(Fund.code))
    existing_codes = {row[0] for row in result.all()}

    from datetime import date as dt_date
    count = 0
    for f in funds:
        code = f["code"]
        if code in existing_codes:
            # Update existing fund
            r = await db.execute(select(Fund).where(Fund.code == code))
            existing = r.scalar_one_or_none()
            if existing:
                if f["fund_size_yi"] is not None:
                    existing.fund_size = f["fund_size_yi"] * 1e8
                if f["type"]:
                    existing.type = f["type"]
                if f["name"]:
                    existing.name = f["name"]
        else:
            db.add(Fund(
                code=code,
                name=f["name"] or "",
                type=f["type"],
                fund_size=f["fund_size_yi"] * 1e8 if f["fund_size_yi"] else None,
            ))
            existing_codes.add(code)
        count += 1

    await db.commit()
    logger.info(f"rankhandler fund list sync: {count} funds upserted ({len(funds)} total from API)")
    return count


async def sync_fund_list(db: AsyncSession):
    """Sync the full fund list from 天天基金."""
    logger.info("Fetching fund list from 天天基金...")
    funds = await fetch_fund_list()
    logger.info(f"Got {len(funds)} funds")

    # Batch query: load existing codes
    result = await db.execute(select(Fund.code))
    existing_codes = {row[0] for row in result.all()}

    for f in funds:
        if f["code"] not in existing_codes:
            db.add(Fund(
                code=f["code"],
                name=f["name"],
                type=f["type"],
            ))

    await db.commit()
    logger.info(f"Fund list synced: {len(funds)} funds")
    return funds


async def sync_fund_detail(code: str, db: AsyncSession):
    """Fetch and save fund detail info."""
    detail = await fetch_fund_detail(code)
    if not detail:
        return

    result = await db.execute(select(Fund).where(Fund.code == code))
    fund = result.scalar_one_or_none()
    if not fund:
        return

    changed = False
    if "fund_size" in detail and detail["fund_size"]:
        fund.fund_size = detail["fund_size"] * 1e8
        changed = True
    if changed:
        await db.commit()


async def _fetch_and_prep_nav(code: str) -> tuple[str, list]:
    """
    Phase 1: Fetch NAV data from remote API (concurrent).
    Returns (code, records_list) — records are deduped against DB.
    """
    # Get latest date in DB (quick lookup)
    async with async_session() as db:
        result = await db.execute(
            select(func.max(FundNav.date)).where(FundNav.fund_code == code)
        )
        latest_date = result.scalar()

    records: list = []
    if latest_date is None:
        # First sync: fetch last 6 months via lsjz with startDate
        from datetime import timedelta
        start = (date.today() - timedelta(days=180)).isoformat()
        records = await fetch_nav_history(code, page_size=MAX_NAV_RECORDS, start_date=start)
    else:
        # Incremental: only fetch records after the latest date
        start = latest_date.isoformat()
        records = await fetch_nav_history(code, page_size=20, start_date=start)
        records = [r for r in records if r["date"] > start]

    return code, records


MAX_NAV_RECORDS = 130  # ~6 months of trading days; signal engine only needs 60


async def trim_nav_records(db: AsyncSession):
    """Trim all funds to latest MAX_NAV_RECORDS using parameterized query."""
    await db.execute(text("""
        DELETE FROM fund_navs WHERE id IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (
                    PARTITION BY fund_code ORDER BY date DESC
                ) AS rn FROM fund_navs
            ) WHERE rn > :max_records
        )
    """), {"max_records": MAX_NAV_RECORDS})
    await db.commit()


async def _save_nav_records(code: str, records: list, db: AsyncSession, skip_dedup: bool = False) -> int:
    """
    Phase 2: Write NAV records to DB (sequential, single session).
    Uses INSERT OR IGNORE with unique constraint for dedup when available.
    Returns number of new records inserted.
    """
    if not records:
        return 0

    if skip_dedup:
        # Bulk insert in batches to avoid OOM (commit every 100 records)
        for i in range(0, len(records), 100):
            batch = records[i:i+100]
            for r in batch:
                db.add(FundNav(
                    fund_code=code,
                    date=datetime.strptime(r["date"], "%Y-%m-%d").date(),
                    nav=r["nav"],
                    acc_nav=r["acc_nav"],
                ))
            await db.commit()
        return len(records)

    # Use INSERT OR IGNORE via the unique constraint for dedup
    count = 0
    for r in records:
        record_date = datetime.strptime(r["date"], "%Y-%m-%d").date()
        db.add(FundNav(
            fund_code=code,
            date=record_date,
            nav=r["nav"],
            acc_nav=r["acc_nav"],
        ))
        count += 1

    if count > 0:
        try:
            await db.commit()
        except Exception:
            # Unique constraint violation — fall back to per-record dedup
            await db.rollback()
            count = 0
            for r in records:
                record_date = datetime.strptime(r["date"], "%Y-%m-%d").date()
                existing = await db.execute(
                    select(FundNav).where(
                        FundNav.fund_code == code,
                        FundNav.date == record_date,
                    )
                )
                if existing.scalar_one_or_none():
                    continue
                db.add(FundNav(
                    fund_code=code,
                    date=record_date,
                    nav=r["nav"],
                    acc_nav=r["acc_nav"],
                ))
                count += 1
            if count > 0:
                await db.commit()

    return count


async def sync_nav(code: str, db: AsyncSession) -> int:
    """
    Single-fund NAV sync (sequential path, used outside batch).
    """
    _code, records = await _fetch_and_prep_nav(code)
    return await _save_nav_records(code, records, db)


async def sync_nav_batch(
    codes: list[str],
    concurrency: int = 10,
    label: str = "",
) -> int:
    """
    Concurrent batch NAV sync.
    Phase 1: HTTP fetches run concurrently (up to `concurrency` at a time).
    Phase 2: DB writes are sequential per small batch (SQLite constraint).
    """
    sem = asyncio.Semaphore(concurrency)
    total = 0
    done = 0
    total_count = len(codes)
    last_log_pct = 0

    # Check if DB is empty — skip per-record dedup if so (much faster)
    async with async_session() as check_db:
        result = await check_db.execute(select(func.count(FundNav.id)))
        skip_dedup = result.scalar() == 0
    if skip_dedup:
        logger.info(f"  [{label}] DB empty, skipping per-record dedup check")

    # Process in small batches to limit memory
    BATCH_SIZE = concurrency * 2  # e.g., 20 funds per batch iteration

    async def _fetch_one(code: str) -> tuple[str, list]:
        async with sem:
            return await _fetch_and_prep_nav(code)

    for i in range(0, total_count, BATCH_SIZE):
        batch = codes[i:i + BATCH_SIZE]

        # Phase 1: Concurrent HTTP fetches with exception isolation
        results = await asyncio.gather(
            *[_fetch_one(c) for c in batch],
            return_exceptions=True,
        )

        # Phase 2: Sequential DB writes (single session, no lock contention)
        async with async_session() as db:
            batch_total = 0
            for result in results:
                if isinstance(result, Exception):
                    logger.warning(f"  [{label}] Fetch error: {result}")
                    continue
                code, records = result
                batch_total += await _save_nav_records(code, records, db, skip_dedup=skip_dedup)

        total += batch_total
        done += len(batch)
        pct = int(done / total_count * 100)
        if pct >= last_log_pct + 5 or done == total_count:
            logger.info(f"  [{label}] NAV sync: {done}/{total_count} ({pct}%), +{total} new records")
            last_log_pct = pct

    # Trim all funds to latest MAX_NAV_RECORDS in one pass
    logger.info(f"  [{label}] Trimming to {MAX_NAV_RECORDS} records per fund...")
    async with async_session() as db:
        await trim_nav_records(db)

    return total


async def sync_holdings(code: str, db: AsyncSession, top_line: int = 10):
    """Sync portfolio holdings for a single fund."""
    records = await fetch_holdings(code, top_line=top_line)
    if not records:
        return 0

    report_date = records[0].get("date", "")
    if not report_date:
        rec_date = date.today()
    else:
        rec_date = datetime.strptime(report_date, "%Y-%m-%d").date()

    await db.execute(
        delete(FundHolding).where(
            FundHolding.fund_code == code,
            FundHolding.date == rec_date,
        )
    )

    count = 0
    for r in records:
        db.add(FundHolding(
            fund_code=code,
            stock_code=r["stock_code"],
            stock_name=r["stock_name"],
            ratio=r["ratio"],
            date=rec_date,
        ))
        count += 1

    await db.commit()
    return count


async def sync_index_quotas(db: AsyncSession):
    """Sync index PE/PB valuation data."""
    records = await fetch_index_quotas()
    if not records:
        logger.warning("No index quota data fetched")
        return 0

    count = 0
    for r in records:
        rec_date = date.fromisoformat(r["date"])
        result = await db.execute(
            select(IndexQuota).where(
                IndexQuota.index_code == r["index_code"],
                IndexQuota.date == rec_date,
            )
        )
        existing = result.scalar_one_or_none()
        if not existing:
            db.add(IndexQuota(
                index_code=r["index_code"],
                name=r["name"],
                pe=r["pe"],
                pb=r["pb"],
                pe_percentile=r["pe_percentile"],
                pb_percentile=r["pb_percentile"],
                date=rec_date,
            ))
            count += 1

    if count > 0:
        await db.commit()

    return count


async def sync_priority_funds(concurrency: int = 10):
    """
    Sync NAV for priority funds only (the top 500 by AUM).
    Uses pingzhongdata for full history fetch, followed by incremental updates.
    """
    logger.info("===== Starting priority fund NAV sync =====")
    async with async_session() as db:
        result = await db.execute(
            select(Fund.code)
            .where(Fund.is_priority == 1)
            .order_by(Fund.code)
        )
        codes = [r[0] for r in result.all()]
        logger.info(f"Priority funds to sync: {len(codes)}")

    total = await sync_nav_batch(codes, concurrency=concurrency, label="Priority")

    logger.info(f"Priority NAV sync complete: +{total} new records across {len(codes)} funds")
    logger.info("===== Priority NAV sync done =====")
    return codes


async def run_full_nav_sync():
    """
    Full NAV sync for all relevant fund types (stock, mixed, index).
    First syncs fund list from rankhandler (with fund_size), then fetches NAV history.
    Uses pingzhongdata (1 req/fund) + concurrency for maximum speed.
    """
    logger.info("===== Starting full NAV sync =====")
    async with async_session() as db:
        # First, update fund list from rankhandler (gets fund_size too)
        await sync_fund_list_from_rankhandler(db)

        result = await db.execute(
            select(Fund.code, Fund.type)
            .where(Fund.type.in_(RELEVANT_TYPES))
            .order_by(Fund.code)
        )
        funds = result.all()
        logger.info(f"Relevant funds to sync: {len(funds)} ({sum(1 for _, t in funds if t == 'stock')} stock, "
              f"{sum(1 for _, t in funds if t == 'mixed')} mixed, "
              f"{sum(1 for _, t in funds if t == 'index')} index)")

        codes = [f[0] for f in funds]

    total = await sync_nav_batch(codes, concurrency=10, label="Full")

    logger.info(f"Full NAV sync complete: +{total} new records across {len(codes)} funds")
    logger.info("===== Full NAV sync done =====")


async def run_daily_collection():
    """Incremental daily NAV collection using rankhandler for batch latest-NAV check.

    1. rankhandler 4 requests → gets latest NAV + fund_size for ALL relevant funds
    2. Compare with DB — only fetch NAV history for funds with outdated data
    3. Skip funds already synced today
    """
    logger.info("===== Starting daily collection =====")
    logger.info("Phase 1: Batch-checking latest NAV via rankhandler...")

    # Phase 1: Get latest NAV from rankhandler for all relevant funds
    try:
        funds = await fetch_funds_from_rankhandler()
    except Exception as e:
        logger.error(f"rankhandler fetch failed: {e}")
        logger.info("Falling back to legacy daily collection")
        return await _legacy_daily_collection()

    if not funds:
        logger.warning("rankhandler returned no data, falling back to legacy daily sync")
        return await _legacy_daily_collection()

    logger.info(f"rankhandler: got {len(funds)} funds with latest NAV dates")

    # Phase 2: Compare with DB, find outdated funds
    today = date.today()
    outdated_codes = []
    fresh_count = 0

    async with async_session() as db:
        # Build lookup of latest DB dates for efficiency
        result = await db.execute(
            select(FundNav.fund_code, func.max(FundNav.date).label("max_date"))
            .group_by(FundNav.fund_code)
        )
        db_dates = {row[0]: row[1] for row in result.all()}

        # Also upsert fund_size from rankhandler while we're at it
        for f in funds:
            code = f["code"]
            latest_db_date = db_dates.get(code)
            nav_date_str = f["nav_date"]

            if latest_db_date and nav_date_str:
                try:
                    rank_date = datetime.strptime(nav_date_str, "%Y-%m-%d").date()
                    if rank_date <= latest_db_date:
                        fresh_count += 1
                        continue
                except ValueError:
                    pass

            outdated_codes.append(code)

            # Upsert fund_size opportunistically
            if f["fund_size_yi"] is not None:
                r = await db.execute(select(Fund).where(Fund.code == code))
                existing = r.scalar_one_or_none()
                if existing:
                    existing.fund_size = f["fund_size_yi"] * 1e8

        await db.commit()

    logger.info(f"Phase 2: {fresh_count} fresh, {len(outdated_codes)} outdated, {len(funds) - fresh_count - len(outdated_codes)} no date data")

    if not outdated_codes:
        logger.info("All funds are up to date, nothing to sync")
        return

    # Phase 3: Only fetch NAV for outdated funds
    total = await sync_nav_batch(outdated_codes, concurrency=15, label="Daily")

    # Phase 4: Index quotas
    async with async_session() as db:
        idx_count = await sync_index_quotas(db)

    logger.info(f"Daily collection done: +{total} NAV records for {len(outdated_codes)} funds, {idx_count} index records")
    logger.info("===== Daily collection complete =====")


async def _legacy_daily_collection():
    """Fallback daily sync — query priority funds directly."""
    logger.info("Using legacy daily collection (no rankhandler data)")
    async with async_session() as db:
        result = await db.execute(
            select(Fund.code)
            .where(Fund.is_priority == 1)
            .order_by(Fund.code)
        )
        codes = [r[0] for r in result.all()]

        if not codes:
            result = await db.execute(
                select(Fund.code)
                .where(Fund.type.in_(RELEVANT_TYPES))
                .order_by(Fund.code)
            )
            codes = [r[0] for r in result.all()]

        logger.info(f"Checking {len(codes)} funds for new NAV data")

    total = await sync_nav_batch(codes, concurrency=15, label="Daily")

    async with async_session() as db:
        idx_count = await sync_index_quotas(db)

    logger.info(f"Legacy daily collection done: +{total} NAV records, {idx_count} index records")


async def run_rankhandler_fund_sync():
    """Standalone fund list sync from rankhandler (just codes + names + sizes, no NAV)."""
    logger.info("===== Starting rankhandler fund list sync =====")
    async with async_session() as db:
        count = await sync_fund_list_from_rankhandler(db)
    logger.info(f"rankhandler fund list sync done: {count} funds upserted")
    logger.info("===== rankhandler fund list sync complete =====")


async def run_full_sync():
    """Legacy full sync (fund list + NAV + holdings + index quotas)."""
    logger.info("===== Starting full data sync =====")
    async with async_session() as db:
        funds = await sync_fund_list(db)
        logger.info(f"Fund list: {len(funds)} funds")

        idx_count = await sync_index_quotas(db)
        logger.info(f"Index quotas: {idx_count} new records")

        relevant = [f for f in funds if f["type"] in RELEVANT_TYPES]
        codes = [f["code"] for f in relevant]

    total_nav = await sync_nav_batch(codes, concurrency=10, label="Full")

    async with async_session() as db:
        logger.info(f"NAV records: {total_nav}")

        total_holdings = 0
        for i, fund in enumerate(relevant):
            h_count = await sync_holdings(fund["code"], db, top_line=10)
            if h_count:
                total_holdings += h_count
            if i % 50 == 0:
                logger.info(f"  Holdings: {i}/{len(relevant)}...")

        logger.info(f"Holdings records: {total_holdings}")
    logger.info("===== Full sync complete =====")
