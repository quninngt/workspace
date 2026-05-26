from pydantic import BaseModel
from datetime import date
from typing import Optional


class AutoConfigResponse(BaseModel):
    id: int
    user_id: int
    total_amount: float
    daily_amount: float
    plan_type: str = "daily"
    status: str
    last_executed_at: Optional[date] = None

    model_config = {"from_attributes": True}


class AutoExecuteResponse(BaseModel):
    ok: bool
    trades_created: int
    total_amount: float
    message: str


class AutoPositionResponse(BaseModel):
    id: int
    fund_code: str
    shares: float
    cost_nav: float
    allocation_ratio: float

    model_config = {"from_attributes": True}


class AutoTradeResponse(BaseModel):
    id: int
    fund_code: str
    type: str
    amount: float
    shares: float
    nav: float
    date: date
    plan_type: str

    model_config = {"from_attributes": True}


class AutoPortfolioResponse(BaseModel):
    id: int
    user_id: int
    cash: float
    total_invested: float
    market_value: float
    positions: list[AutoPositionResponse] = []
    trades: list[AutoTradeResponse] = []

    model_config = {"from_attributes": True}


class AutoReportResponse(BaseModel):
    id: int
    period_type: str
    period_start: date
    period_end: date
    stats: Optional[str] = None

    model_config = {"from_attributes": True}
