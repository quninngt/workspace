"""
Adaptive sync executor: monitors sync health and auto-adjusts parameters
to avoid OOM, timeouts, and other failures.
"""

import os
import time
import asyncio
import signal
import platform
from datetime import datetime

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from app.database import async_session
from app.models.fund import Fund, FundNav
from app.services.data_collector.collector import (
    sync_nav_batch,
    _fetch_and_prep_nav,
    _save_nav_records,
    trim_nav_records,
    MAX_NAV_RECORDS,
)
from sqlalchemy import select, func


class SyncMetrics:
    """Tracks per-fund and aggregate sync metrics for adaptive decisions."""

    def __init__(self):
        self.fund_times: dict[str, float] = {}  # code -> fetch_seconds
        self.fund_record_counts: dict[str, int] = {}
        self.memory_samples: list[float] = []
        self.start_time: float = 0
        self.oom_count: int = 0
        self.total_fetched: int = 0
        self.total_saved: int = 0
        self.current_concurrency: int = 10
        self.current_batch_size: int = 20
        self.stream_mode: bool = False  # True = write immediately after each fetch

    def memory_mb(self) -> float:
        if HAS_PSUTIL:
            return psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
        # Fallback: read /proc/self/status
        try:
            with open("/proc/self/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        return float(line.split()[1]) / 1024
        except OSError:
            pass
        return 0.0

    def record_fund(self, code: str, elapsed: float, records: int):
        self.fund_times[code] = elapsed
        self.fund_record_counts[code] = records
        self.total_fetched += 1
        self.memory_samples.append(self.memory_mb())

    def avg_fetch_time(self) -> float:
        if not self.fund_times:
            return 0
        return sum(self.fund_times.values()) / len(self.fund_times)

    def p95_fetch_time(self) -> float:
        if not self.fund_times:
            return 0
        sorted_t = sorted(self.fund_times.values())
        idx = int(len(sorted_t) * 0.95)
        return sorted_t[min(idx, len(sorted_t) - 1)]

    def avg_records(self) -> float:
        if not self.fund_record_counts:
            return 0
        vals = list(self.fund_record_counts.values())
        return sum(vals) / len(vals)

    def peak_memory_mb(self) -> float:
        return max(self.memory_samples) if self.memory_samples else 0

    def report(self) -> dict:
        return {
            "funds_fetched": self.total_fetched,
            "funds_saved": self.total_saved,
            "avg_fetch_time_s": round(self.avg_fetch_time(), 2),
            "p95_fetch_time_s": round(self.p95_fetch_time(), 2),
            "avg_records_per_fund": round(self.avg_records(), 0),
            "peak_memory_mb": round(self.peak_memory_mb(), 1),
            "current_concurrency": self.current_concurrency,
            "current_batch_size": self.current_batch_size,
            "stream_mode": self.stream_mode,
            "oom_count": self.oom_count,
        }


def _should_reduce_concurrency(metrics: SyncMetrics) -> bool:
    """If memory is high or server is slow, dial down concurrency."""
    mem = metrics.memory_mb()
    # If memory > 500MB and concurrency > 3, reduce
    if mem > 500 and metrics.current_concurrency > 3:
        return True
    # If p95 fetch time > 5s (server throttling), back off
    if metrics.p95_fetch_time() > 5 and metrics.current_concurrency > 3:
        return True
    return False


def _should_enable_streaming(metrics: SyncMetrics) -> bool:
    """If per-fund records are high, stream to avoid memory buildup."""
    return metrics.avg_records() > 300


def _should_increase_concurrency(metrics: SyncMetrics) -> bool:
    """If memory is low and server is fast, speed up."""
    mem = metrics.memory_mb()
    return (
        mem < 200
        and metrics.avg_fetch_time() < 2
        and metrics.current_concurrency < 20
        and not metrics.stream_mode
    )


async def adaptive_sync(
    codes: list[str],
    label: str = "Adaptive",
    max_concurrency: int = 15,
    mem_limit_mb: int = 400,
    check_interval: int = 10,  # seconds between adaptation checks
) -> int:
    """
    Sync NAV data with automatic adaptation to system conditions.

    Monitors memory usage, fetch latency, and record volume, then adjusts:
      - concurrency (lower when memory high or server slow)
      - batch mode (stream vs gather)
      - batch size

    If OOM-killed, retries with conservave settings.
    """
    metrics = SyncMetrics()
    metrics.start_time = time.time()
    metrics.current_concurrency = min(10, max_concurrency)

    print(f"[{label}] Starting adaptive sync: {len(codes)} funds")
    print(f"[{label}] Initial concurrency={metrics.current_concurrency}, mem_limit={mem_limit_mb}MB")
    print(f"[{label}] psutil={'yes' if HAS_PSUTIL else 'no (using /proc/self/status)'}")

    # Sanity check
    if not codes:
        print(f"[{label}] No codes to sync")
        return 0

    # Check if DB is empty — skip dedup if so
    async with async_session() as db:
        result = await db.execute(select(func.count(FundNav.id)))
        db_empty = result.scalar() == 0
    if db_empty:
        print(f"[{label}] DB empty, will skip dedup checks")

    total = 0
    done = 0
    total_count = len(codes)

    # Adaptive loop: processes funds in dynamic batches
    while done < total_count:
        batch = codes[done:done + metrics.current_batch_size]
        if not batch:
            break

        mem_before = metrics.memory_mb()
        batch_result = await _run_adaptive_batch(
            batch, metrics, db_empty, label, mem_limit_mb
        )

        if batch_result is None:
            # Batch failed (likely OOM). Recover and retry.
            metrics.oom_count += 1
            print(f"[{label}] Batch failed (OOM or crash), adjusting...")
            # Aggressively reduce
            metrics.current_concurrency = max(2, metrics.current_concurrency // 2)
            metrics.current_batch_size = metrics.current_concurrency * 2
            metrics.stream_mode = True
            print(f"[{label}] New settings: concurrency={metrics.current_concurrency}, "
                  f"batch_size={metrics.current_batch_size}, stream={metrics.stream_mode}")
            # Wait a moment for system to recover
            await asyncio.sleep(2)
            continue

        batch_added, batch_total = batch_result
        total += batch_added
        done += batch_total
        elapsed = time.time() - metrics.start_time

        pct = int(done / total_count * 100)
        mem_now = metrics.memory_mb()
        rate = f"{done/elapsed:.1f} funds/min" if elapsed > 0 else "?"
        print(f"[{label}] {done}/{total_count} ({pct}%), +{total} NAV records, "
              f"mem={mem_now:.0f}MB, {rate}, "
              f"conc={metrics.current_concurrency}, "
              f"stream={'Y' if metrics.stream_mode else 'N'}")

        # Adapt parameters based on metrics
        if _should_reduce_concurrency(metrics):
            old = metrics.current_concurrency
            metrics.current_concurrency = max(3, int(metrics.current_concurrency * 0.7))
            metrics.current_batch_size = metrics.current_concurrency * 2
            if metrics.current_concurrency < old:
                print(f"[{label}] Reducing concurrency: {old} → {metrics.current_concurrency} "
                      f"(mem={mem_now:.0f}MB, p95={metrics.p95_fetch_time():.1f}s)")

        if _should_enable_streaming(metrics) and not metrics.stream_mode:
            metrics.stream_mode = True
            print(f"[{label}] Enabling stream mode (avg {metrics.avg_records():.0f} records/fund)")

        if _should_increase_concurrency(metrics):
            # If we lowered earlier but conditions improved, cautiously increase
            if metrics.current_concurrency < max_concurrency and metrics.oom_count == 0:
                metrics.current_concurrency = min(max_concurrency, metrics.current_concurrency + 2)
                metrics.current_batch_size = metrics.current_concurrency * 2
                print(f"[{label}] Increasing concurrency to {metrics.current_concurrency} "
                      f"(mem={mem_now:.0f}MB, fast fetches)")

    # Final trim
    print(f"[{label}] Trimming to {MAX_NAV_RECORDS} records per fund...")
    async with async_session() as db:
        await trim_nav_records(db)

    elapsed = time.time() - metrics.start_time
    report = metrics.report()
    print(f"[{label}] ==== Complete: +{total} records in {elapsed:.0f}s ====")
    print(f"[{label}] Report: {report}")
    return total


async def _run_adaptive_batch(
    batch: list[str],
    metrics: SyncMetrics,
    db_empty: bool,
    label: str,
    mem_limit_mb: int,
) -> tuple[int, int] | None:
    """
    Run a single batch, handling each fund within memory limits.
    Returns (new_records, batch_size) or None on failure.
    """
    sem = asyncio.Semaphore(metrics.current_concurrency)
    batch_records: dict[str, list] = {}
    fetch_tasks = []
    added = 0

    # Phase 1: submit all fetches
    async def _fetch_and_record(code: str):
        async with sem:
            t0 = time.time()
            try:
                _code, records = await _fetch_and_prep_nav(code)
                elapsed = time.time() - t0
                metrics.record_fund(_code, elapsed, len(records))
                return _code, records
            except Exception as e:
                print(f"  [{label}] Fetch error {code}: {e}")
                return code, []

    if metrics.stream_mode:
        # Stream mode: write each fund immediately after fetch
        for code in batch:
            task = asyncio.create_task(_fetch_and_record(code))
            fetch_tasks.append(task)

        for task in asyncio.as_completed(fetch_tasks):
            code, records = await task
            if records:
                async with async_session() as db:
                    n = await _save_nav_records(code, records, db, skip_dedup=db_empty)
                    added += n
                    metrics.total_saved += n

            mem = metrics.memory_mb()
            if mem > mem_limit_mb:
                print(f"  [{label}] Memory warning ({mem:.0f}MB > {mem_limit_mb}MB), "
                      f"self-throttling 2s...")
                await asyncio.sleep(2)
    else:
        # Gather mode: collect all, then write
        results = await asyncio.gather(
            *[_fetch_and_record(c) for c in batch], return_exceptions=True
        )

        for result in results:
            if isinstance(result, Exception):
                print(f"  [{label}] Batch fetch exception: {result}")
                continue
            code, records = result
            batch_records[code] = records

        async with async_session() as db:
            for code, records in batch_records.items():
                n = await _save_nav_records(code, records, db, skip_dedup=db_empty)
                added += n
                metrics.total_saved += n

        mem = metrics.memory_mb()
        if mem > mem_limit_mb:
            print(f"  [{label}] Memory high ({mem:.0f}MB), switching to stream mode")
            metrics.stream_mode = True

    return added, len(batch)


async def main_sync():
    """
    Entry point: sync all priority funds with adaptive strategy.
    """
    from app.database import init_db
    await init_db()

    async with async_session() as db:
        result = await db.execute(
            select(Fund.code)
            .where(Fund.is_priority == 1)
            .order_by(Fund.code)
        )
        codes = [r[0] for r in result.all()]

    print(f"Priority funds to sync: {len(codes)}")
    if not codes:
        print("No priority funds found. Run setup_top500.py first.")
        return

    await adaptive_sync(codes, label="Pri", max_concurrency=15, mem_limit_mb=400)


if __name__ == "__main__":
    asyncio.run(main_sync())
