from pydantic import BaseModel
from datetime import date
from typing import Optional


class ExecutionItemResponse(BaseModel):
    id: int
    user_id: int
    plan_type: str
    fund_code: str
    action: str
    suggested_amount_min: Optional[float] = None
    suggested_amount_max: Optional[float] = None
    signal_id: Optional[int] = None
    status: str
    date: date

    model_config = {"from_attributes": True}


class ExecutionItemCreate(BaseModel):
    plan_type: str  # daily/weekly/monthly
    fund_code: str
    action: str  # buy/sell/hold
    suggested_amount_min: Optional[float] = None
    suggested_amount_max: Optional[float] = None


class SubmitExecutionResponse(BaseModel):
    trades_created: int
    total_amount: float
    portfolio_id: int | None = None
    portfolio_name: str = ""


class ExecutionItemUpdate(BaseModel):
    action: Optional[str] = None
    suggested_amount_min: Optional[float] = None
    suggested_amount_max: Optional[float] = None
    status: Optional[str] = None


class ManualPortfolioResponse(BaseModel):
    id: int
    user_id: int
    name: str
    cash: float
    total_invested: float
    positions: list["ManualPositionResponse"] = []
    trades: list["ManualTradeResponse"] = []

    model_config = {"from_attributes": True}


class ManualPositionResponse(BaseModel):
    id: int
    fund_code: str
    shares: float
    cost_nav: float

    model_config = {"from_attributes": True}


class ManualTradeResponse(BaseModel):
    id: int
    fund_code: str
    type: str
    amount: float
    shares: float
    nav: float
    date: date

    model_config = {"from_attributes": True}
