"""
Migration script: Add unique constraints and indexes to existing SQLite database.
Run once: python3 migrate_unique_constraints.py
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "cumbre.db")


def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}, nothing to migrate.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Check if constraints already exist
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cur.fetchall()}

    migrations = []

    # 1. fund_navs: UniqueConstraint(fund_code, date) + index
    if "fund_navs" in tables:
        cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='fund_navs'")
        create_sql = cur.fetchone()[0]
        if "uq_fund_nav_code_date" not in create_sql:
            # Deduplicate
            cur.execute("""
                DELETE FROM fund_navs WHERE rowid NOT IN (
                    SELECT MIN(rowid) FROM fund_navs GROUP BY fund_code, date
                )
            """)
            dupes_removed = cur.rowcount
            # Recreate table with constraint
            cur.execute("ALTER TABLE fund_navs RENAME TO fund_navs_old")
            cur.execute("""
                CREATE TABLE fund_navs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fund_code VARCHAR(20) NOT NULL,
                    date DATE NOT NULL,
                    nav FLOAT NOT NULL,
                    acc_nav FLOAT NOT NULL,
                    UNIQUE (fund_code, date)
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS ix_fund_nav_code_date ON fund_navs(fund_code, date)")
            cur.execute("CREATE INDEX IF NOT EXISTS ix_fund_navs_fund_code ON fund_navs(fund_code)")
            cur.execute("""
                INSERT INTO fund_navs (id, fund_code, date, nav, acc_nav)
                SELECT id, fund_code, date, nav, acc_nav FROM fund_navs_old
            """)
            cur.execute("DROP TABLE fund_navs_old")
            migrations.append(f"fund_navs: added unique constraint (removed {dupes_removed} duplicates)")

    # 2. signals: UniqueConstraint(fund_code, date) + index on date
    if "signals" in tables:
        cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='signals'")
        create_sql = cur.fetchone()[0]
        if "uq_signal_code_date" not in create_sql:
            cur.execute("""
                DELETE FROM signals WHERE rowid NOT IN (
                    SELECT MIN(rowid) FROM signals GROUP BY fund_code, date
                )
            """)
            dupes_removed = cur.rowcount
            cur.execute("ALTER TABLE signals RENAME TO signals_old")
            cur.execute("""
                CREATE TABLE signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fund_code VARCHAR(20) NOT NULL,
                    date DATE NOT NULL,
                    score FLOAT NOT NULL,
                    level VARCHAR(1) NOT NULL,
                    action VARCHAR(10) NOT NULL,
                    factors_detail TEXT,
                    recommendation TEXT,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (fund_code, date)
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS ix_signal_date ON signals(date)")
            cur.execute("CREATE INDEX IF NOT EXISTS ix_signals_fund_code ON signals(fund_code)")
            cur.execute("""
                INSERT INTO signals (id, fund_code, date, score, level, action, factors_detail, recommendation, created_at)
                SELECT id, fund_code, date, score, level, action, factors_detail, recommendation, created_at FROM signals_old
            """)
            cur.execute("DROP TABLE signals_old")
            migrations.append(f"signals: added unique constraint (removed {dupes_removed} duplicates)")

    # 3. watchlists: UniqueConstraint(user_id, fund_code)
    if "watchlists" in tables:
        cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='watchlists'")
        create_sql = cur.fetchone()[0]
        if "uq_watchlist_user_fund" not in create_sql:
            cur.execute("""
                DELETE FROM watchlists WHERE rowid NOT IN (
                    SELECT MIN(rowid) FROM watchlists GROUP BY user_id, fund_code
                )
            """)
            dupes_removed = cur.rowcount
            cur.execute("ALTER TABLE watchlists RENAME TO watchlists_old")
            cur.execute("""
                CREATE TABLE watchlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    fund_code VARCHAR(20) NOT NULL,
                    group_name VARCHAR(100) NOT NULL DEFAULT '默认',
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (user_id, fund_code)
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS ix_watchlists_user_id ON watchlists(user_id)")
            cur.execute("""
                INSERT INTO watchlists (id, user_id, fund_code, group_name, created_at)
                SELECT id, user_id, fund_code, group_name, created_at FROM watchlists_old
            """)
            cur.execute("DROP TABLE watchlists_old")
            migrations.append(f"watchlists: added unique constraint (removed {dupes_removed} duplicates)")

    # 4. auto_configs: UniqueConstraint(user_id)
    if "auto_configs" in tables:
        cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='auto_configs'")
        create_sql = cur.fetchone()[0]
        if "uq_auto_config_user" not in create_sql:
            cur.execute("""
                DELETE FROM auto_configs WHERE rowid NOT IN (
                    SELECT MIN(rowid) FROM auto_configs GROUP BY user_id
                )
            """)
            dupes_removed = cur.rowcount
            cur.execute("ALTER TABLE auto_configs RENAME TO auto_configs_old")
            cur.execute("""
                CREATE TABLE auto_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    total_amount FLOAT NOT NULL DEFAULT 0,
                    daily_amount FLOAT NOT NULL DEFAULT 0,
                    plan_type VARCHAR(10) NOT NULL DEFAULT 'daily',
                    status VARCHAR(20) NOT NULL DEFAULT 'active',
                    last_executed_at DATE,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (user_id)
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS ix_auto_configs_user_id ON auto_configs(user_id)")
            cur.execute("""
                INSERT INTO auto_configs (id, user_id, total_amount, daily_amount, plan_type, status, last_executed_at, created_at)
                SELECT id, user_id, total_amount, daily_amount, plan_type, status, last_executed_at, created_at FROM auto_configs_old
            """)
            cur.execute("DROP TABLE auto_configs_old")
            migrations.append(f"auto_configs: added unique constraint (removed {dupes_removed} duplicates)")

    # 5. Add is_admin column to users if missing
    if "users" in tables:
        cur.execute("PRAGMA table_info(users)")
        columns = {row[1] for row in cur.fetchall()}
        if "is_admin" not in columns:
            cur.execute("ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0")
            migrations.append("users: added is_admin column")

    # 6. Add created_at to auto_trades if missing
    if "auto_trades" in tables:
        cur.execute("PRAGMA table_info(auto_trades)")
        columns = {row[1] for row in cur.fetchall()}
        if "created_at" not in columns:
            cur.execute("ALTER TABLE auto_trades ADD COLUMN created_at DATETIME")
            migrations.append("auto_trades: added created_at column")

    conn.commit()
    conn.close()

    if migrations:
        print("Migration complete:")
        for m in migrations:
            print(f"  - {m}")
    else:
        print("No migrations needed.")


if __name__ == "__main__":
    migrate()
