from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class WatchlistResponse(BaseModel):
    id: int
    user_id: int
    fund_code: str
    group_name: str
    created_at: datetime

    model_config = {"from_attributes": True}
