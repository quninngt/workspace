#!/usr/bin/env python3
"""Monitor grid scan progress by checking the SQLite DB directly."""
import sqlite3
import json
from datetime import datetime

DB_PATH = "/home/ubuntu/workspace/stu/cumbre/backend/cumbre.db"

try:
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        "SELECT id, name, created_at, performance, summary FROM backtest_results ORDER BY id DESC LIMIT 3"
    ).fetchall()
    conn.close()

    if not rows:
        print("⏳ 网格扫描尚未产生任何结果（仍在运行中，42个回测 ~预计30分钟）")
        exit(0)

    # Find grid scan result
    grid = None
    for r in rows:
        if r["name"] and r["name"].startswith("[网格]"):
            grid = r
            break

    if not grid:
        print("⏳ 网格扫描尚未写入数据库（仍在运行中）")
        exit(0)

    # Get full detail including daily_values for ranked results
    detail_row = conn.execute(
        "SELECT daily_values FROM backtest_results WHERE id = ?", (grid["id"],)
    ).fetchone()
    conn.close()

    perf = json.loads(grid["performance"]) if grid["performance"] else {}
    summary = json.loads(grid["summary"]) if grid["summary"] else {}

    total_return = perf.get("total_return_pct", 0)
    sharpe = perf.get("sharpe_ratio", 0)

    # Check if real results or placeholder (still running)
    if total_return == 0 and sharpe == 0:
        print("⏳ 网格扫描尚未完成（当前结果全是 0，后台还在跑）")
        exit(0)

    # Real results - print full report
    improvement = summary.get("improvement", {})
    best_label = summary.get("best_label", "未知")
    candidates = summary.get("candidates_tried", 0)
    successful = summary.get("successful_runs", 0)

    lines = []
    lines.append(f"✅ 网格扫描完成！")
    lines.append(f"尝试 {candidates} 种组合，成功 {successful} 种")
    lines.append(f"")
    lines.append(f"🏆 最优策略: {best_label}")
    lines.append(f"   Sharpe: {sharpe}")
    lines.append(f"   总收益: {total_return}%")
    lines.append(f"   年化收益: {perf.get('annualized_return_pct', 0)}%")
    lines.append(f"   最大回撤: -{perf.get('max_drawdown_pct', 0)}%")
    lines.append(f"   胜率: {perf.get('win_rate_pct', 0)}%")
    lines.append(f"   基准收益: {perf.get('benchmark_return_pct', 0)}%")

    if improvement:
        lines.append(f"")
        lines.append(f"📈 vs 默认参数:")
        if improvement.get("sharpe_improvement"):
            lines.append(f"   Sharpe {'↑' if improvement['sharpe_improvement'] > 0 else '↓'} {improvement['sharpe_improvement']:+.2f}")
        if improvement.get("return_improvement_pct"):
            lines.append(f"   收益 {'↑' if improvement['return_improvement_pct'] > 0 else '↓'} {improvement['return_improvement_pct']:+.2f}%")
        if improvement.get("max_dd_reduction_pct"):
            dd = improvement["max_dd_reduction_pct"]
            lines.append(f"   回撤 {'↓' if dd > 0 else '↑'} {abs(dd):.2f}%")

    # Process daily_values for ranked results
    if detail_row and detail_row["daily_values"]:
        ranked = json.loads(detail_row["daily_values"])
        if ranked and len(ranked) > 0:
            lines.append(f"")
            lines.append(f"📊 Top 10:")
            lines.append(f"{'排名':<4} {'策略':<16} {'Sharpe':<7} {'收益%':<7} {'回撤%':<7} {'年化%':<7}")
            lines.append("-" * 55)
            for i, r in enumerate(ranked[:10]):
                p = r.get("performance", {})
                sharpe_v = p.get("sharpe_ratio", 0) or 0
                ret_v = p.get("total_return_pct", 0) or 0
                dd_v = p.get("max_drawdown_pct", 0) or 0
                ann_v = p.get("annualized_return_pct", 0) or 0
                label = r.get("label", "?")[:14]
                lines.append(f"{i+1:<4} {label:<16} {sharpe_v:<7.2f} {ret_v:<7.2f} {dd_v:<7.2f} {ann_v:<7.2f}")

    print("\n".join(lines))

except Exception as e:
    print(f"⚠️ 监控检查出错: {e}")
