"""
Scheduler service: manages periodic tasks for data collection and signal generation.
Runs daily after market close (~20:00 Beijing time).
"""

import logging
import time
import os
import fcntl
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

# Minimum signal count to consider the signal engine as "completed successfully"
_MIN_SIGNAL_COUNT = 1000

# Lock file for preventing concurrent job execution
_LOCK_FILE = "/tmp/cumbre_scheduler.lock"


async def _run_step(step_name: str, coro):
    """Run a step with timing and error isolation."""
    t0 = time.time()
    try:
        await coro
        logger.info(f"  ✓ {step_name} ({time.time()-t0:.0f}s)")
        return True
    except Exception as e:
        logger.error(f"  ✗ {step_name} FAILED after {time.time()-t0:.0f}s: {e}", exc_info=True)
        return False


class _FileLock:
    """Simple file-based lock for preventing concurrent scheduler jobs."""

    def __init__(self, path: str):
        self._path = path
        self._fd = None

    def acquire(self) -> bool:
        try:
            self._fd = open(self._path, "w")
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._fd.write(str(os.getpid()))
            self._fd.flush()
            return True
        except (IOError, OSError):
            if self._fd:
                self._fd.close()
                self._fd = None
            return False

    def release(self):
        if self._fd:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
                self._fd.close()
            except (IOError, OSError):
                pass
            self._fd = None


_job_lock = _FileLock(_LOCK_FILE)


async def daily_job():
    """Daily after-market job: collect data, generate signals, execute auto trades."""
    if not _job_lock.acquire():
        logger.warning("Daily job skipped — another job is already running")
        return

    try:
        from app.database import init_db, async_session
        from app.services.data_collector.collector import run_daily_collection
        from app.services.signal_engine.engine import run_signal_engine
        from app.services.auto_executor import run_auto_executor
        from datetime import date

        logger.info("=== Starting daily job ===")
        t_start = time.time()
        await init_db()

        nav_ok = await _run_step("NAV 增量同步", run_daily_collection())
        sig_ok = await _run_step("信号引擎", run_signal_engine(target_date=date.today()))

        if sig_ok:
            async with async_session() as db:
                await _run_step("自动跟投执行", run_auto_executor(db, target_date=date.today()))

        logger.info(f"=== Daily job complete ({time.time()-t_start:.0f}s) ===")
    finally:
        _job_lock.release()


async def full_sync_job():
    """Weekly full sync: fund list, NAV, index quotas, signals, auto execution."""
    if not _job_lock.acquire():
        logger.warning("Full sync job skipped — another job is already running")
        return

    try:
        from app.database import init_db, async_session
        from app.services.data_collector.collector import (
            run_rankhandler_fund_sync,
            run_daily_collection,
        )
        from app.services.signal_engine.engine import run_signal_engine
        from app.services.auto_executor import run_auto_executor
        from datetime import date

        logger.info("=== Starting weekly full sync ===")
        t_start = time.time()
        await init_db()

        # Step 1: Update fund list + fund_size from rankhandler
        await _run_step("基金列表同步", run_rankhandler_fund_sync())

        # Step 2: Incremental NAV check + index quota sync
        nav_ok = await _run_step("NAV 增量同步 + 指数估值", run_daily_collection())

        # Step 3: Generate signals for all funds
        sig_ok = await _run_step("信号引擎", run_signal_engine(target_date=date.today()))

        # Step 4: Execute auto trades (only if signals were generated)
        if sig_ok:
            async with async_session() as db:
                await _run_step("自动跟投执行", run_auto_executor(db, target_date=date.today()))

        logger.info(f"=== Weekly full sync complete ({time.time()-t_start:.0f}s) ===")
    finally:
        _job_lock.release()


def start_scheduler():
    """Start the background scheduler with daily trigger."""
    scheduler.add_job(
        daily_job,
        CronTrigger(hour=20, minute=30, timezone="Asia/Shanghai"),
        id="daily_collection",
        replace_existing=True,
    )

    scheduler.add_job(
        full_sync_job,
        CronTrigger(day_of_week="sun", hour=21, minute=0, timezone="Asia/Shanghai"),
        id="weekly_full_sync",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started: daily 20:30, weekly Sun 21:00 (Asia/Shanghai)")


async def catchup_if_needed():
    """Check if today's signal engine and auto executor have run; if not, run them on startup."""
    from datetime import date
    from app.database import async_session
    from sqlalchemy import select, func
    from app.models.signal import Signal
    from app.models.auto import AutoTrade

    today = date.today()

    # 1. Check signals — verify count is reasonable, not just non-zero
    async with async_session() as db:
        result = await db.execute(select(func.count(Signal.id)).where(Signal.date == today))
        signal_count = result.scalar() or 0

    if signal_count < _MIN_SIGNAL_COUNT:
        if signal_count > 0:
            logger.warning(f"📋 Only {signal_count} signals for {today} (expected >{_MIN_SIGNAL_COUNT}), re-running...")
        else:
            logger.info(f"📋 No signals for {today}, running signal engine...")
        from app.services.signal_engine.engine import run_signal_engine
        await _run_step("信号引擎补跑", run_signal_engine(target_date=today))
    else:
        logger.info(f"✅ Signals already exist for {today} ({signal_count})")

    # 2. Check auto execution (independent of signals check)
    async with async_session() as db:
        result = await db.execute(
            select(func.count(AutoTrade.id)).where(AutoTrade.date == today)
        )
        trade_count = result.scalar() or 0

    if trade_count == 0:
        logger.info(f"📋 No auto trades for {today}, running auto executor...")
        from app.services.auto_executor import run_auto_executor
        async with async_session() as db:
            await _run_step("自动跟投补跑", run_auto_executor(db, target_date=today))
    else:
        logger.info(f"✅ Auto trades already exist for {today} ({trade_count})")

    if signal_count >= _MIN_SIGNAL_COUNT and trade_count > 0:
        logger.info(f"✅ Startup catchup skipped — all tasks already ran for {today}")
    else:
        logger.info(f"✅ Startup catchup complete for {today}")
