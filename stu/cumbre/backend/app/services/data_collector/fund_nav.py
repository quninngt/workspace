"""
Fetch historical NAV data from 天天基金.
Sources:
  - pingzhongdata/{code}.js  →  ALL NAV records in ONE request (fast, initial sync)
  - api.fund.eastmoney.com/f10/lsjz  →  paginated, supports date range (incremental)
"""

import re
import json
import logging
import asyncio
from datetime import datetime
from typing import TypedDict
import httpx

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_BACKOFF = 1.0  # seconds, doubles each retry


class NavRecord(TypedDict):
    date: str       # "2026-05-14"
    nav: float      # unit NAV (单位净值)
    acc_nav: float  # accumulated NAV (累计净值)


async def _request_with_retry(client: httpx.AsyncClient, method: str, url: str, **kwargs) -> httpx.Response:
    """HTTP request with exponential backoff retry."""
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
                logger.warning(f"  HTTP {method} attempt {attempt+1} failed: {e}, retrying in {wait}s")
                await asyncio.sleep(wait)
    raise last_exc


async def fetch_nav_from_pingzhong(code: str) -> list[NavRecord]:
    """
    Fetch ALL historical NAV records from pingzhongdata JS.
    One HTTP request returns the full history — much faster than the paginated lsjz API.
    Falls back to lsjz if pingzhongdata doesn't contain Data_netWorthTrend.
    """
    url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://fund.eastmoney.com/",
    }

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await _request_with_retry(client, "GET", url, headers=headers)
        except Exception:
            # 301 redirect → notfound.html (fund without pingzhongdata)
            return []

        text = resp.text
        if len(text) < 100:
            return []
        match = re.search(r"var Data_netWorthTrend\s*=\s*(\[.*?\]);", text, re.DOTALL)
        if not match:
            return []

        try:
            raw = json.loads(match.group(1))
        except json.JSONDecodeError:
            return []

        records = []
        for r in raw:
            try:
                ts = r.get("x")  # timestamp in ms
                nav_val = float(r.get("y", 0))
                if not ts or nav_val == 0:
                    continue
                dt = datetime.fromtimestamp(ts / 1000)
                date_str = dt.strftime("%Y-%m-%d")
                # pingzhongdata only has unit nav; set acc_nav = nav as fallback
                records.append(NavRecord(
                    date=date_str,
                    nav=nav_val,
                    acc_nav=nav_val,
                ))
            except (ValueError, KeyError):
                continue

        # Oldest first (pingzhongdata returns newest-first usually)
        # Actually let's return newest-first to match the existing convention
        records.reverse()  # pingzhongdata is oldest-first
        return records


async def fetch_nav_history(
    code: str,
    page_size: int = 20,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[NavRecord]:
    """
    Fetch historical NAV data via the paginated lsjz API.
    Returns newest-first list of NavRecords.
    Use start_date for incremental fetching.
    """
    url = "https://api.fund.eastmoney.com/f10/lsjz"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://fund.eastmoney.com/",
    }

    per_page = 20
    total_needed = min(page_size, 2000)
    pages_needed = (total_needed + per_page - 1) // per_page

    all_records = []
    async with httpx.AsyncClient(timeout=15) as client:
        for page_index in range(1, pages_needed + 1):
            params = {
                "callback": "jQuery",
                "fundCode": code,
                "pageIndex": page_index,
                "pageSize": 50,
            }
            if start_date:
                params["startDate"] = start_date
            if end_date:
                params["endDate"] = end_date

            try:
                resp = await _request_with_retry(client, "GET", url, headers=headers, params=params)
            except Exception as e:
                logger.warning(f"  NAV fetch error for {code} page {page_index}: {e}")
                break

            text = resp.text
            match = re.search(r"jQuery\((.*)\)", text, re.DOTALL)
            if not match:
                break

            data = json.loads(match.group(1))
            if data.get("ErrCode") != 0:
                break

            records = data.get("Data", {}).get("LSJZList", [])
            if not records:
                break

            for r in records:
                try:
                    nav_val = float(r["DWJZ"]) if r.get("DWJZ") and r["DWJZ"] != "" else 0
                    acc_val = float(r["LJJZ"]) if r.get("LJJZ") and r["LJJZ"] != "" else 0
                    if nav_val == 0:
                        continue
                    all_records.append(NavRecord(
                        date=r["FSRQ"],
                        nav=nav_val,
                        acc_nav=acc_val,
                    ))
                except (ValueError, KeyError):
                    continue

            if len(all_records) >= total_needed:
                all_records = all_records[:total_needed]
                break

    return all_records


async def fetch_latest_nav(code: str) -> NavRecord | None:
    """Fetch the latest NAV record for a fund."""
    records = await fetch_nav_history(code, page_size=1)
    return records[0] if records else None
