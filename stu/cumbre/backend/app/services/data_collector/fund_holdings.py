"""
Fetch fund portfolio holdings from 天天基金.
Source: https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=jjcc
"""

import re
import html
from typing import TypedDict
import httpx
from bs4 import BeautifulSoup


class HoldingRecord(TypedDict):
    stock_code: str
    stock_name: str
    ratio: float       # percentage of portfolio
    date: str          # quarter-end date


async def fetch_holdings(code: str, top_line: int = 10) -> list[HoldingRecord]:
    """
    Fetch the latest portfolio holdings for a fund.
    Returns a list of HoldingRecords.
    Uses the 天天基金 fund holdings API with proper Referer header.
    """
    url = "https://fundf10.eastmoney.com/FundArchivesDatas.aspx"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": f"https://fundf10.eastmoney.com/ccmx_{code}.html",
    }

    params = {
        "type": "jjcc",
        "code": code,
        "topline": top_line,
        "year": "",
        "month": "",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, headers=headers, params=params)
        resp.raise_for_status()

    text = resp.text

    # Extract date from the page
    date_match = re.search(r"截止至：(\d{4}-\d{2}-\d{2})", text)
    report_date = date_match.group(1) if date_match else ""

    # Extract the HTML content from JavaScript wrapper
    # Format: var apidata={ content:"<html...>",arryear:[...],curyear:...};
    start_marker = 'content:"'
    s = text.find(start_marker)
    if s < 0:
        return []

    start = s + len(start_marker)
    # Find the closing " of the content string
    # The content ends when we find ",arryear or ",curyear or similar
    remaining = text[start:]

    # Look for patterns that indicate the end of content
    # The content is followed by ",arryear: or ", which signals the end
    end_match = re.search(r'",\s*[a-zA-Z_]+\s*:', remaining)
    if end_match:
        raw_html = remaining[:end_match.start()]
    else:
        # Fallback: find next unescaped quote followed by comma
        end_match2 = re.search(r'"(?=\s*[,}])', remaining)
        if end_match2:
            raw_html = remaining[:end_match2.start()]
        else:
            return []

    # Unescape: \' -> ', \/ -> /, \\ -> \, etc.
    raw_html = (raw_html
        .replace("\\'", "'")
        .replace('\\"', '"')
        .replace("\\/", "/")
        .replace("\\r", "")
        .replace("\\n", "")
        .replace("\\t", "")
    )

    # Handle unicode escape sequences only if present
    if "\\u" in raw_html:
        raw_html = raw_html.encode("utf-8").decode("unicode_escape")

    # Decode HTML entities (&nbsp; etc.)
    raw_html = html.unescape(raw_html)

    soup = BeautifulSoup(raw_html, "html.parser")
    table = soup.find("table")
    if not table:
        return []

    data_rows = table.find_all("tr")
    # Filter out header rows (they contain th, not td)
    data_rows = [r for r in data_rows if r.find("td")]

    results = []
    for row in data_rows:
        cells = row.find_all("td")
        if len(cells) < 7:
            continue

        # Column order: 序号, 股票代码, 股票名称, 最新价, 涨跌幅, 相关资讯, 占净值比例
        code_cell = cells[1]
        name_cell = cells[2]
        ratio_cell = cells[6]

        # Extract stock code from link or text
        stock_code = code_cell.get_text(strip=True)
        link = code_cell.find("a")
        if link and link.get("href"):
            code_match = re.search(r"/(?:sz|sh)?(\d{6})", link["href"])
            if code_match:
                stock_code = code_match.group(1)

        stock_name = name_cell.get_text(strip=True)

        ratio_text = ratio_cell.get_text(strip=True).replace("%", "").replace(",", "")
        try:
            ratio = float(ratio_text)
        except ValueError:
            continue

        if stock_code and stock_name:
            results.append(HoldingRecord(
                stock_code=stock_code,
                stock_name=stock_name,
                ratio=ratio,
                date=report_date,
            ))

    return results
