from pydantic import BaseModel
from datetime import date
from typing import Optional


class SignalResponse(BaseModel):
    id: int
    fund_code: str
    date: date
    score: float
    level: str
    action: str
    factors_detail: Optional[str] = None
    recommendation: Optional[str] = None

    model_config = {"from_attributes": True}
