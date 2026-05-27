"""
Risk metrics module: calculates risk profile for individual funds.

Metrics:
- Annualized Volatility: daily_returns.std() × √252
- 95% VaR: daily_returns.quantile(0.05) — worst daily loss at 95% confidence
- Sharpe Ratio: (annualized_return - risk_free_rate) / volatility
- Max Drawdown: peak-to-trough decline + recovery days
- Risk Level: low (< 10%), medium (10-20%), high (> 20%)
"""

import logging
import math
from typing import Optional

logger = logging.getLogger(__name__)

# Risk-free rate: ~2% (1-year China government bond yield)
RISK_FREE_RATE = 0.02

# Volatility thresholds for risk level classification
VOL_LOW = 0.10    # < 10% annualized vol → low risk
VOL_HIGH = 0.20   # > 20% annualized vol → high risk


def calculate_risk_metrics(nav_values: list[float]) -> dict:
    """
    Calculate risk metrics from NAV history.

    Args:
        nav_values: List of NAV values in chronological order (oldest first)

    Returns:
        {
            "volatility": float,           # annualized volatility (0.15 = 15%)
            "var_95": float,               # 95% VaR as negative return (-0.03 = -3%)
            "sharpe_ratio": float | None,  # Sharpe ratio (None if insufficient data)
            "max_drawdown": float,         # max drawdown as negative fraction (-0.20 = -20%)
            "max_drawdown_days": int | None,  # days to recover from max drawdown (None if not recovered)
            "risk_level": str,             # "low" / "medium" / "high"
            "total_return": float,         # total return over period (0.15 = 15%)
            "annualized_return": float,    # annualized return
            "trading_days": int,           # number of trading days in dataset
        }
    """
    if len(nav_values) < 2:
        return _default_metrics(len(nav_values))

    # Calculate daily returns
    returns = []
    for i in range(1, len(nav_values)):
        if nav_values[i - 1] > 0:
            returns.append(nav_values[i] / nav_values[i - 1] - 1)

    if not returns:
        return _default_metrics(len(nav_values))

    n = len(returns)
    trading_days = len(nav_values)

    # Annualized volatility
    daily_vol = _std(returns)
    volatility = daily_vol * math.sqrt(252)

    # 95% VaR (historical simulation)
    sorted_returns = sorted(returns)
    var_index = max(0, int(n * 0.05) - 1)
    var_95 = sorted_returns[var_index]

    # Total and annualized return
    total_return = nav_values[-1] / nav_values[0] - 1
    years = trading_days / 252
    if years > 0 and (1 + total_return) > 0:
        annualized_return = (1 + total_return) ** (1 / years) - 1
    else:
        annualized_return = 0.0

    # Sharpe ratio
    if volatility > 0:
        sharpe_ratio = (annualized_return - RISK_FREE_RATE) / volatility
    else:
        sharpe_ratio = None

    # Max drawdown + recovery days
    max_dd, recovery_days = _max_drawdown(nav_values)

    # Risk level
    if volatility < VOL_LOW:
        risk_level = "low"
    elif volatility > VOL_HIGH:
        risk_level = "high"
    else:
        risk_level = "medium"

    return {
        "volatility": round(volatility, 4),
        "var_95": round(var_95, 4),
        "sharpe_ratio": round(sharpe_ratio, 2) if sharpe_ratio is not None else None,
        "max_drawdown": round(max_dd, 4),
        "max_drawdown_days": recovery_days,
        "risk_level": risk_level,
        "total_return": round(total_return, 4),
        "annualized_return": round(annualized_return, 4),
        "trading_days": trading_days,
    }


def _std(values: list[float]) -> float:
    """Standard deviation of a list."""
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / (n - 1)
    return math.sqrt(variance)


def _max_drawdown(nav_values: list[float]) -> tuple[float, Optional[int]]:
    """
    Calculate max drawdown and recovery days.

    Returns:
        (max_drawdown, recovery_days)
        max_drawdown is negative (e.g., -0.20 for 20% drawdown)
        recovery_days is None if never recovered
    """
    if not nav_values:
        return 0.0, None

    peak = nav_values[0]
    peak_idx = 0
    max_dd = 0.0
    max_dd_peak_idx = 0
    max_dd_trough_idx = 0

    for i, v in enumerate(nav_values):
        if v > peak:
            peak = v
            peak_idx = i
        dd = (v - peak) / peak if peak > 0 else 0
        if dd < max_dd:
            max_dd = dd
            max_dd_peak_idx = peak_idx
            max_dd_trough_idx = i

    # Check if recovered
    recovery_days = None
    if max_dd < 0 and max_dd_peak_idx < len(nav_values) - 1:
        trough_nav = nav_values[max_dd_trough_idx]
        peak_nav = nav_values[max_dd_peak_idx]
        for i in range(max_dd_trough_idx + 1, len(nav_values)):
            if nav_values[i] >= peak_nav:
                recovery_days = i - max_dd_trough_idx
                break

    return max_dd, recovery_days


def _default_metrics(trading_days: int) -> dict:
    """Default metrics when insufficient data."""
    return {
        "volatility": 0.0,
        "var_95": 0.0,
        "sharpe_ratio": None,
        "max_drawdown": 0.0,
        "max_drawdown_days": None,
        "risk_level": "medium",  # conservative default
        "total_return": 0.0,
        "annualized_return": 0.0,
        "trading_days": trading_days,
    }
