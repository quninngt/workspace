"""
Momentum factor: calculates scores based on RSI and MACD.

RSI: oversold (<30) = buy, overbought (>70) = sell
MACD: bullish crossover = buy, bearish crossover = sell
"""

from typing import TypedDict


class MomentumResult(TypedDict):
    score: float        # 0-100
    details: dict


def calculate_momentum(nav_values: list[float]) -> MomentumResult:
    """
    Calculate momentum factor score from NAV history.
    Higher score = stronger buy signal.

    Uses RSI and MACD to gauge momentum.
    """
    if len(nav_values) < 26:
        return MomentumResult(score=50.0, details={"reason": "insufficient data"})

    close_prices = nav_values
    current = close_prices[-1]

    # RSI (Relative Strength Index) - 60% weight
    rsi = _rsi(close_prices, 14)
    rsi_score = _rsi_to_score(rsi)

    # MACD (Moving Average Convergence Divergence) - 40% weight
    macd_line, signal_line = _macd(close_prices)
    macd_value = macd_line[-1] - signal_line[-1] if macd_line and signal_line else 0
    # Normalize MACD to a 0-100 score

    # If MACD is near zero, score is neutral
    # If MACD histogram is positive and growing = bullish
    prev_macd_value = macd_line[-2] - signal_line[-2] if len(macd_line) > 1 and len(signal_line) > 1 else 0
    macd_slope = macd_value - prev_macd_value

    # Normalize MACD value to a score
    macd_score = _normalize_macd(macd_value, current)
    macd_slope_score = _normalize_macd(macd_slope, current * 0.01)

    combined_macd = macd_score * 0.5 + macd_slope_score * 0.5

    # Final: RSI 60%, MACD 40%
    final_score = rsi_score * 0.6 + combined_macd * 0.4

    return MomentumResult(
        score=round(final_score, 1),
        details={
            "rsi": round(rsi, 2),
            "rsi_score": round(rsi_score, 1),
            "macd_value": round(macd_value, 4),
            "macd_slope": round(macd_slope, 4),
            "macd_score": round(combined_macd, 1),
        },
    )


def _rsi(values: list[float], period: int = 14) -> float:
    """Calculate RSI."""
    if len(values) < period + 1:
        return 50.0

    deltas = [values[i] - values[i - 1] for i in range(-period, 0)]
    avg_gain = sum(d for d in deltas if d > 0) / period
    avg_loss = abs(sum(d for d in deltas if d < 0)) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _rsi_to_score(rsi: float) -> float:
    """Convert RSI to a 0-100 buy signal score.
    RSI < 30 (oversold) → high buy score (80-100)
    RSI > 70 (overbought) → low buy score (0-20)
    """
    if rsi <= 30:
        # Oversold: strong buy signal
        return 80 + (30 - rsi) / 30 * 20
    elif rsi >= 70:
        # Overbought: strong sell signal
        return max(0, 20 - (rsi - 70) / 30 * 20)
    else:
        # Neutral zone: inverse linear from 80 at 30 to 20 at 70
        return 80 - (rsi - 30) / 40 * 60


def _ema(values: list[float], period: int) -> list[float]:
    """Exponential Moving Average."""
    if not values:
        return []
    multiplier = 2 / (period + 1)
    result = [values[0]]
    for v in values[1:]:
        result.append((v - result[-1]) * multiplier + result[-1])
    return result


def _macd(values: list[float]) -> tuple[list[float], list[float]]:
    """Calculate MACD line and signal line."""
    ema12 = _ema(values, 12)
    ema26 = _ema(values, 26)

    # MACD line = EMA12 - EMA26
    macd_line = [e12 - e26 for e12, e26 in zip(ema12, ema26)]

    # Signal line = EMA9 of MACD line
    signal_line = _ema(macd_line, 9)

    return macd_line, signal_line


def _normalize_macd(value: float, ref: float) -> float:
    """Normalize MACD value to a 0-100 score. Positive MACD signals
    upward momentum (bullish), negative signals downward (bearish)."""
    if ref == 0:
        return 50.0

    ratio = value / ref * 100  # as percentage of price
    if ratio >= 2:
        return 100.0
    elif ratio <= -2:
        return 0.0
    elif ratio >= 0:
        return 50 + ratio / 2 * 50
    else:
        return 50 + ratio / 2 * 50
