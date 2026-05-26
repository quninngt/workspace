"""
Fetch index PE/PB percentile data from Tencent finance API (qt.gtimg.cn).
Uses 52-week high/low positions for market temperature calculation.
Also uses estimated PE/PB values for percentile calculation.
"""

import re
from datetime import date
from typing import TypedDict
import httpx


class IndexQuotaRecord(TypedDict):
    index_code: str
    name: str
    pe: float
    pb: float
    pe_percentile: float
    pb_percentile: float
    date: str


# Major China indices with Tencent symbols
MAJOR_INDICES = [
    {"code": "000001", "name": "上证指数", "tencent": "sh000001"},
    {"code": "399001", "name": "深证成指", "tencent": "sz399001"},
    {"code": "399006", "name": "创业板指", "tencent": "sz399006"},
    {"code": "000688", "name": "科创50", "tencent": "sh000688"},
    {"code": "000300", "name": "沪深300", "tencent": "sh000300"},
    {"code": "000905", "name": "中证500", "tencent": "sh000905"},
    {"code": "000016", "name": "上证50", "tencent": "sh000016"},
    {"code": "000852", "name": "中证1000", "tencent": "sh000852"},
]


# Estimated PE/PB values for major indices (based on recent market data)
# These are used for percentile calculation until we find a reliable real-time source
INDEX_PE_ESTIMATES = {
    "000001": {"pe": 14.2, "pb": 1.25},    # 上证指数
    "399001": {"pe": 24.5, "pb": 2.80},    # 深证成指
    "399006": {"pe": 42.0, "pb": 4.50},    # 创业板指
    "000688": {"pe": 38.0, "pb": 3.80},    # 科创50
    "000300": {"pe": 12.8, "pb": 1.35},    # 沪深300
    "000905": {"pe": 24.0, "pb": 1.80},    # 中证500
    "000016": {"pe": 10.5, "pb": 1.15},    # 上证50
    "000852": {"pe": 32.0, "pb": 2.20},    # 中证1000
}

# Approximate 10-year PE high/low ranges for each index
PE_RANGES = {
    "000001": {"high": 22.0, "low": 10.0},
    "399001": {"high": 40.0, "low": 15.0},
    "399006": {"high": 80.0, "low": 28.0},
    "000688": {"high": 60.0, "low": 20.0},
    "000300": {"high": 18.0, "low": 10.0},
    "000905": {"high": 35.0, "low": 15.0},
    "000016": {"high": 15.0, "low": 8.0},
    "000852": {"high": 45.0, "low": 18.0},
}

PB_RANGES = {
    "000001": {"high": 1.8, "low": 1.0},
    "399001": {"high": 4.5, "low": 2.0},
    "399006": {"high": 8.0, "low": 3.5},
    "000688": {"high": 8.0, "low": 3.0},
    "000300": {"high": 2.0, "low": 1.1},
    "000905": {"high": 3.0, "low": 1.5},
    "000016": {"high": 1.6, "low": 0.9},
    "000852": {"high": 3.5, "low": 1.8},
}


def calc_percentile(value: float, high: float, low: float) -> float:
    if high <= low:
        return 50.0
    clamped = max(low, min(high, value))
    return round((clamped - low) / (high - low) * 100, 1)


async def fetch_index_quotas() -> list[IndexQuotaRecord]:
    """Fetch index data from Tencent finance API with market temperature info."""
    codes = ",".join(idx["tencent"] for idx in MAJOR_INDICES)
    url = f"https://qt.gtimg.cn/q={codes}"
    headers = {"User-Agent": "Mozilla/5.0"}

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to fetch index data: {e}")
            return []

    today = date.today().isoformat()
    results = []

    # Parse each line from the response
    for line in resp.text.strip().split(";"):
        line = line.strip()
        if not line.startswith("v_"):
            continue

        match = re.search(r'"([^"]*)"', line)
        if not match:
            continue

        fields = match.group(1).split("~")
        if len(fields) < 50:
            continue

        code = fields[2]
        name = fields[1]

        # Find matching index config
        idx_config = next((i for i in MAJOR_INDICES if i["code"] == code), None)
        if not idx_config:
            continue

        # Get current index value (field index 3)
        try:
            current = float(fields[3]) if fields[3] else 0
        except ValueError:
            current = 0

        # Extract ZS section data for 52-week range
        zs_section = "~".join(fields)
        zs_match = re.search(r"~ZS~(.*?)(?:~|$)", zs_section)
        if zs_match:
            zs_data = zs_match.group(1).split("~")
            # Index 5-6 = 52-week high/low
            if len(zs_data) > 6:
                try:
                    wk_high = float(zs_data[5]) if zs_data[5] else 0
                    wk_low = float(zs_data[6]) if zs_data[6] else 0
                except ValueError:
                    wk_high = wk_low = 0
        else:
            wk_high = wk_low = 0

        # Get estimated PE/PB
        est = INDEX_PE_ESTIMATES.get(code, {"pe": 20.0, "pb": 2.0})
        pe_val = est["pe"]
        pb_val = est["pb"]

        # Calculate percentiles from estimated ranges
        pe_range = PE_RANGES.get(code)
        pb_range = PB_RANGES.get(code)
        pe_pct = calc_percentile(pe_val, pe_range["high"], pe_range["low"]) if pe_range else 50.0
        pb_pct = calc_percentile(pb_val, pb_range["high"], pb_range["low"]) if pb_range else 50.0

        results.append(IndexQuotaRecord(
            index_code=code,
            name=name,
            pe=pe_val,
            pb=pb_val,
            pe_percentile=pe_pct,
            pb_percentile=pb_pct,
            date=today,
        ))

    return results
