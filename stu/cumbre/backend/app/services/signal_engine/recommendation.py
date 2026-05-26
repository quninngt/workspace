"""
Recommendation descriptions for signals.
Generates professional (专业版) and plain-language (通俗版) explanations
for each signal based on factor scores and fund characteristics.
"""

from __future__ import annotations

# ── factor thresholds ──
HIGH_THRESH = 60  # factor score above this = bullish contributor
LOW_THRESH = 40   # factor score below this = bearish contributor

FACTOR_CN = {
    "valuation": "估值",
    "trend": "趋势",
    "momentum": "动量",
    "quality": "质量",
    "sentiment": "情绪",
}

FUND_TYPE_CN = {
    "stock": "股票型",
    "mixed": "混合型",
    "index": "指数型",
    "bond": "债券型",
    "etf": "ETF",
    "qdii": "QDII",
    "money": "货币型",
}

LEVEL_ACTION_CN = {
    ("S", "buy"): "强势买入",
    ("A", "buy"): "建议买入",
    ("B", "hold"): "建议持有",
    ("C", "sell"): "建议减仓",
    ("D", "sell"): "强烈建议卖出",
}

# ── factor-specific detail readers ──

def _valuation_detail(details: dict) -> str:
    """Extract key valuation detail for display."""
    dd = details.get("valuation", {})
    nav_range = dd.get("nav_52w_range_pct")
    reversal = dd.get("short_term_reversal_5d")
    parts = []
    if nav_range is not None:
        parts.append(f"52周NAV处于历史{nav_range:.0f}%分位")
    if reversal is not None and reversal < 0:
        parts.append(f"近5日回落{abs(reversal):.1f}%")
    return "，".join(parts) if parts else ""


def _trend_detail(details: dict) -> str:
    dd = details.get("trend", {})
    cross = dd.get("crossover_pct")
    dev = dd.get("deviation_pct")
    parts = []
    if cross is not None:
        direction = "金叉" if cross > 0 else "死叉"
        parts.append(f"MA20/MA60{direction}({cross:+.2f}%)")
    if dev is not None:
        parts.append(f"价格偏离MA20 {dev:+.2f}%")
    return "，".join(parts)


def _momentum_detail(details: dict) -> str:
    dd = details.get("momentum", {})
    rsi = dd.get("rsi")
    macd = dd.get("macd_value")
    parts = []
    if rsi is not None:
        parts.append(f"RSI {rsi:.1f}")
    if macd is not None:
        parts.append(f"MACD {macd:+.4f}")
    return "，".join(parts)


def _quality_detail(details: dict) -> str:
    dd = details.get("quality", {})
    parts = []
    size = dd.get("size")
    dd_val = dd.get("drawdown") or dd.get("calc_drawdown")
    if size is not None:
        parts.append(f"规模分{size:.0f}")
    if dd_val is not None:
        parts.append(f"回撤分{dd_val:.0f}")
    cons = dd.get("consistency")
    if cons is not None:
        parts.append(f"稳定性分{cons:.0f}")
    return "，".join(parts) if parts else ""


def _sentiment_detail(details: dict) -> str:
    dd = details.get("sentiment", {})
    parts = []
    vol = dd.get("vol_20d_pct")
    trend = dd.get("vol_trend_10d_60d")
    dd_pct = dd.get("drawdown_pct")
    if vol is not None:
        parts.append(f"20日波动率{vol:.2f}%")
    if trend is not None:
        parts.append(f"波动趋势{'上升' if trend and trend > 1.1 else '平稳' if trend and trend > 0.9 else '下降'}")
    if dd_pct is not None and dd_pct > 1:
        parts.append(f"近20日回撤{dd_pct:.1f}%")
    return "，".join(parts) if parts else ""


FACTOR_DETAIL_FN = {
    "valuation": _valuation_detail,
    "trend": _trend_detail,
    "momentum": _momentum_detail,
    "quality": _quality_detail,
    "sentiment": _sentiment_detail,
}

FACTOR_HIGH_CN = {
    "valuation": "估值偏低",
    "trend": "趋势向好",
    "momentum": "动量强势",
    "quality": "质量优秀",
    "sentiment": "市场恐慌(反向机会)",
}

FACTOR_LOW_CN = {
    "valuation": "估值偏高",
    "trend": "趋势走弱",
    "momentum": "动量不足",
    "quality": "质量一般",
    "sentiment": "市场情绪平淡",
}

FACTOR_PLAIN_HIGH = {
    "valuation": "价格处于相对低位，比较划算",
    "trend": "走势向上，表现积极",
    "momentum": "上涨动力充足",
    "quality": "基金本身质量不错，管理稳定",
    "sentiment": "近期市场波动较大，部分投资者可能恐慌卖出，反而是逆势布局的机会",
}

FACTOR_PLAIN_LOW = {
    "valuation": "价格处于相对高位，性价比不高",
    "trend": "走势偏弱，表现不佳",
    "momentum": "上涨动力不足",
    "quality": "基金本身质量有待提高",
    "sentiment": "近期市场较为平稳，没有明显的恐慌或狂热情绪",
}


def generate_recommendation(
    fund_name: str,
    fund_type: str | None,
    level: str,
    action: str,
    score: float,
    factor_scores: dict[str, float],
    factor_details: dict,
) -> dict:
    """
    Generate professional and plain-language recommendation descriptions.

    Returns:
        {
            "short": str,          # one-line action summary
            "professional": str,   # detailed technical analysis
            "plain": str,          # plain language explanation
        }
    """
    # Determine top positive and negative factors
    positive = [f for f, v in factor_scores.items() if v >= HIGH_THRESH]
    negative = [f for f, v in factor_scores.items() if v <= LOW_THRESH]
    positive.sort(key=lambda f: factor_scores[f], reverse=True)
    negative.sort(key=lambda f: factor_scores[f])

    type_cn = FUND_TYPE_CN.get(fund_type or "", fund_type or "")
    action_cn = LEVEL_ACTION_CN.get((level, action), f"{level}级-{action}")

    # ── short (one-liner) ──
    short_parts = []
    if positive:
        short_parts.append("+".join(FACTOR_HIGH_CN[f] for f in positive[:2]))
    if negative:
        short_parts.append("注意" + "、".join(FACTOR_LOW_CN[f] for f in negative[:2]))

    if action == "buy":
        suffix = f"，建议逢低分批建仓"
    elif action == "sell":
        suffix = f"，建议逐步减仓控制风险"
    else:
        suffix = f"，建议继续持有观望"

    if short_parts:
        short = "；".join(short_parts) + suffix
    else:
        short = f"各因子表现均衡{action_cn}，{suffix.lstrip('，')}"

    # ── professional ──
    prof_lines = [f"【{action_cn}】{fund_name}（{type_cn}）综合评分{score:.1f}分"]
    prof_lines.append("")

    if positive:
        prof_lines.append("▶ 主要利好因素：")
        for f in positive[:3]:
            detail = FACTOR_DETAIL_FN.get(f, lambda _: "")(factor_details)
            detail_str = f"（{detail}）" if detail else ""
            prof_lines.append(f"  • {FACTOR_CN[f]}：{FACTOR_HIGH_CN[f]}{detail_str}")

    if negative:
        prof_lines.append("▶ 主要风险因素：")
        for f in negative[:2]:
            prof_lines.append(f"  • {FACTOR_CN[f]}：{FACTOR_LOW_CN[f]}")

    # Factor breakdown line
    factor_line = " | ".join(
        f"{FACTOR_CN[f]} {v:.0f}" for f, v in sorted(factor_scores.items(), key=lambda x: x[1], reverse=True)
    )
    prof_lines.append("")
    prof_lines.append(f"▶ 因子得分：{factor_line}")

    professional = "\n".join(prof_lines)

    # ── plain language ──
    plain_lines = [f"{fund_name}目前综合评分{score:.1f}分，评级为{action_cn}。"]

    if action == "buy":
        plain_lines.append("简单来说，这只基金目前各方面表现不错，建议可以适量买入。")
    elif action == "sell":
        plain_lines.append("目前该基金面临一定压力，建议适当减少持有量，降低风险。")
    else:
        plain_lines.append("目前表现平稳，没有明显的买入或卖出信号，建议继续持有观察。")

    # Add specific plain-language points
    reasons = []
    for f in positive[:2]:
        reasons.append(FACTOR_PLAIN_HIGH.get(f, ""))
    for f in negative[:1]:
        reasons.append(FACTOR_PLAIN_LOW.get(f, ""))
    if reasons:
        plain_lines.append("判断依据：" + "；".join(reasons))

    plain = "\n".join(plain_lines)

    return {
        "short": short,
        "professional": professional,
        "plain": plain,
    }
