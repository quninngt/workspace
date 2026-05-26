"""
Fetch all China public fund codes, names, and types from 天天基金.
Source: https://fund.eastmoney.com/js/fundcode_search.js
"""

import json
import logging
import re
from typing import TypedDict
import httpx

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_BACKOFF = 1.0  # seconds, doubles each retry


class FundInfo(TypedDict):
    code: str
    name: str
    type: str  # e.g. "混合型-灵活", "股票型", "债券型-混合二级"


FUND_TYPE_MAP = {
    "股票型": "stock",
    "混合型": "mixed",
    "债券型": "bond",
    "指数型": "index",
    "ETF": "etf",
    "QDII": "qdii",
    "货币型": "money_market",
    "FOF": "fof",
    "REITs": "reits",
}


def map_fund_type(raw_type: str) -> str:
    for keyword, mapped in FUND_TYPE_MAP.items():
        if keyword in raw_type:
            return mapped
    return "other"


async def _request_with_retry(client: httpx.AsyncClient, method: str, url: str, **kwargs) -> httpx.Response:
    """HTTP request with exponential backoff retry."""
    import asyncio
    last_exc = None
    for attempt in range(_MAX_RETRIES):
        try:
            resp = await client.request(method, url, **kwargs)
            resp.raise_for_status()
            return resp
        except (httpx.HTTPStatusError, httpx.TransportError) as e:
            last_exc = e
            if attempt < _MAX_RETRIES - 1:
                wait = _RETRY_BACKOFF * (2 ** attempt)
                logger.warning(f"  HTTP {method} {url} attempt {attempt+1} failed: {e}, retrying in {wait}s")
                await asyncio.sleep(wait)
    raise last_exc


async def fetch_fund_list() -> list[FundInfo]:
    """
    Fetch the complete fund list from 天天基金.
    Returns a list of FundInfo dicts.
    """
    url = "https://fund.eastmoney.com/js/fundcode_search.js"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://fund.eastmoney.com/",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await _request_with_retry(client, "GET", url, headers=headers)

    text = resp.text
    # Parse: var r = [["code","name","type","pinyin","abbr"], ...]
    match = re.search(r"var r = (\[.*?\]);", text, re.DOTALL)
    if not match:
        raise ValueError("Failed to parse fund list JS")

    raw = json.loads(match.group(1))
    funds = []
    for item in raw:
        code = item[0]
        name = item[2]      # item[1] is pinyin abbr, item[2] is Chinese name
        raw_type = item[3]  # e.g. "混合型-灵活", "股票型"
        fund_type = map_fund_type(raw_type)
        funds.append(FundInfo(code=code, name=name, type=fund_type))

    return funds


async def fetch_fund_detail(code: str) -> dict | None:
    """
    Fetch fund detail from pingzhongdata JS.
    Returns parsed data or None if not found.
    """
    url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://fund.eastmoney.com/",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await _request_with_retry(client, "GET", url, headers=headers)
        except Exception:
            return None

    text = resp.text
    data = {}

    # Extract fund name
    m = re.search(r'var fS_name\s*=\s*"([^"]+)"', text)
    if m:
        data["name"] = m.group(1)

    # Extract fund code
    m = re.search(r'var fS_code\s*=\s*"([^"]+)"', text)
    if m:
        data["code"] = m.group(1)

    # Extract fund rate
    m = re.search(r'var fund_sourceRate\s*=\s*"([^"]+)"', text)
    if m:
        data["source_rate"] = m.group(1)

    # Extract fund size (亿)
    m = re.search(r'var fund_size\s*=\s*([\d.]+)', text)
    if m:
        data["fund_size"] = float(m.group(1))

    # Extract stock holdings codes
    m = re.search(r'var stockCodes\s*=\s*\[([^\]]*)\]', text)
    if m:
        codes_str = m.group(1).strip()
        if codes_str:
            data["stock_codes"] = [c.strip().strip('"') for c in codes_str.split(",")]

    return data if data else None
