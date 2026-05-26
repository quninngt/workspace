from pydantic import BaseModel
from datetime import date
from typing import Optional


class BacktestParams(BaseModel):
    initial_capital: float = 1_000_000
    factor_weights: dict[str, float] | None = None
    buy_weights: dict[str, float] = {"S": 2.0, "A": 1.0}
    sell_ratios: dict[str, float] = {"C": 0.25, "D": 0.50}
    max_single_fund_ratio: float = 0.30
    max_daily_buys: int = 5
    signal_thresholds: dict[str, float] | None = None
    normalize_signals: bool = False


class BacktestRequest(BaseModel):
    start_date: date
    end_date: date
    name: str = ""
    params: BacktestParams | None = None


class BacktestResultResponse(BaseModel):
    id: int
    name: str
    start_date: date
    end_date: date
    params: Optional[str] = None
    performance: Optional[str] = None
    summary: Optional[str] = None
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


class BacktestResultDetailResponse(BaseModel):
    id: int
    name: str
    start_date: date
    end_date: date
    params: Optional[str] = None
    performance: Optional[str] = None
    signal_distribution: Optional[str] = None
    factor_contributions: Optional[str] = None
    monthly_returns: Optional[str] = None
    daily_values: Optional[str] = None
    summary: Optional[str] = None
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}
