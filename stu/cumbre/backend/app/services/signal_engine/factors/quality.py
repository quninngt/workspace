"""
Quality factor: scores based on fund stability and manager skill.
- Fund size stability
- Manager tenure
- Maximum drawdown
- NAV return consistency (positive-return day ratio)
- Fund age

Weight in overall model: 30%
"""

from typing import TypedDict


class QualityResult(TypedDict):
    score: float
    details: dict


def calculate_quality(
    fund_size: float | None = None,
    manager_tenure_years: float | None = None,
    max_drawdown_pct: float | None = None,
    nav_values: list[float] | None = None,
    fund_age_years: float | None = None,
) -> QualityResult:
    """
    Calculate quality factor score based on fund fundamentals.

    Higher score = better quality = more suitable for buying.
    """
    scores = []

    # Fund size score (25% of quality)
    if fund_size is not None:
        if fund_size <= 0:
            size_score = 30
        elif fund_size <= 1:
            size_score = 40
        elif fund_size <= 10:
            size_score = 60
        elif fund_size <= 50:
            size_score = 75
        elif fund_size <= 100:
            size_score = 85
        else:
            size_score = 90
        scores.append(("size", size_score, 0.25))

    # Manager tenure score (25% of quality)
    if manager_tenure_years is not None:
        if manager_tenure_years <= 0:
            tenure_score = 30
        elif manager_tenure_years <= 1:
            tenure_score = 45
        elif manager_tenure_years <= 3:
            tenure_score = 65
        elif manager_tenure_years <= 5:
            tenure_score = 80
        else:
            tenure_score = 90
        scores.append(("tenure", tenure_score, 0.25))

    # Max drawdown score (25% of quality)
    dd_computed = False
    if max_drawdown_pct is not None:
        dd = abs(max_drawdown_pct)
        if dd <= 10:
            dd_score = 90
        elif dd <= 20:
            dd_score = 75
        elif dd <= 30:
            dd_score = 55
        elif dd <= 40:
            dd_score = 35
        elif dd <= 50:
            dd_score = 20
        else:
            dd_score = 10
        scores.append(("drawdown", dd_score, 0.25))
        dd_computed = True

    # Calc drawdown from NAV data if not provided
    if not dd_computed and nav_values and len(nav_values) > 20:
        peak = nav_values[0]
        max_dd = 0
        for v in nav_values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak * 100
            if dd > max_dd:
                max_dd = dd
        dd_score = max(10, 100 - max_dd * 2)
        scores.append(("calc_drawdown", dd_score, 0.25))

    # NAV return consistency (15% of quality) — NEW
    # Measures manager's ability to generate positive returns consistently
    if nav_values and len(nav_values) >= 20:
        positive_days = 0
        total_days = 0
        for i in range(1, len(nav_values)):
            prev = nav_values[i - 1]
            curr = nav_values[i]
            if prev > 0:
                total_days += 1
                if curr >= prev:
                    positive_days += 1

        if total_days > 0:
            pos_ratio = positive_days / total_days
            # > 60% → excellent, > 55% → good, > 50% → average, > 45% → below avg
            if pos_ratio >= 0.60:
                consistency_score = 85
            elif pos_ratio >= 0.55:
                consistency_score = 68
            elif pos_ratio >= 0.50:
                consistency_score = 50
            elif pos_ratio >= 0.45:
                consistency_score = 32
            else:
                consistency_score = 18
            scores.append(("consistency", consistency_score, 0.15))

    # Fund age score (10% of quality)
    if fund_age_years is not None:
        if fund_age_years <= 0.5:
            age_score = 30
        elif fund_age_years <= 1:
            age_score = 45
        elif fund_age_years <= 3:
            age_score = 60
        elif fund_age_years <= 5:
            age_score = 75
        else:
            age_score = 85
        scores.append(("age", age_score, 0.10))

    if not scores:
        return QualityResult(score=50.0, details={"reason": "no quality data"})

    final_score = sum(s * w for _, s, w in scores) / sum(w for _, _, w in scores)

    return QualityResult(
        score=round(final_score, 1),
        details={
            factor: round(s, 1) for factor, s, _ in scores
        },
    )
