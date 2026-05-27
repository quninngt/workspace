"""
Macro signal API: market environment indicator.
"""

from datetime import date
from fastapi import APIRouter, Query
from app.services.signal_engine.macro import get_macro_signal

router = APIRouter(prefix="/api/macro-signal", tags=["macro"])


@router.get("")
async def macro_signal(date_str: str = Query(None, alias="date", description="日期 YYYY-MM-DD")):
    """
    获取宏观市场信号。

    基于沪深300 PE/PB 百分位判断市场环境：
    - risk_on: 估值偏低（PE百分位 < 30%），适合积极配置
    - neutral: 估值中性（30%-70%）
    - risk_off: 估值偏高（PE百分位 > 70%），建议防守

    返回:
    - signal: risk_on / neutral / risk_off
    - multiplier: 信号引擎评分折扣系数 (1.0 / 0.92 / 0.75)
    - pe_percentile / pb_percentile: 当前估值百分位
    - reasoning: 中文说明
    """
    target = date.fromisoformat(date_str) if date_str else None
    result = await get_macro_signal(target)
    return result
