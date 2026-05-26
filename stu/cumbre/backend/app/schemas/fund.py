from pydantic import BaseModel
from datetime import date
from typing import Optional


class FundResponse(BaseModel):
    code: str
    name: str
    type: str
    company: Optional[str] = None
    fund_size: Optional[float] = None
    risk_level: Optional[str] = None
    manager_id: Optional[str] = None
    established_date: Optional[date] = None

    model_config = {"from_attributes": True}


class FundNavResponse(BaseModel):
    date: date
    nav: float
    acc_nav: float

    model_config = {"from_attributes": True}


class FundValuationResponse(BaseModel):
    date: date
    pe: Optional[float] = None
    pb: Optional[float] = None
    pe_percentile: Optional[float] = None
    pb_percentile: Optional[float] = None

    model_config = {"from_attributes": True}


class FundHoldingResponse(BaseModel):
    stock_code: Optional[str] = None
    stock_name: Optional[str] = None
    ratio: Optional[float] = None
    date: date

    model_config = {"from_attributes": True}


class FundManagerResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    tenure: Optional[str] = None
    fund_codes: Optional[str] = None

    model_config = {"from_attributes": True}


class IndexQuotaResponse(BaseModel):
    index_code: str
    name: Optional[str] = None
    pe: Optional[float] = None
    pb: Optional[float] = None
    pe_percentile: Optional[float] = None
    pb_percentile: Optional[float] = None
    date: date

    model_config = {"from_attributes": True}
