from app.schemas.auth import (
    RegisterRequest, LoginRequest, AuthResponse, UserResponse,
)
from app.schemas.fund import (
    FundResponse, FundNavResponse, FundValuationResponse,
    FundHoldingResponse, FundManagerResponse, IndexQuotaResponse,
)
from app.schemas.signal import SignalResponse
from app.schemas.auto import (
    AutoConfigResponse, AutoPortfolioResponse, AutoPositionResponse,
    AutoTradeResponse, AutoReportResponse,
)
from app.schemas.manual import (
    ExecutionItemResponse, ExecutionItemCreate, ExecutionItemUpdate,
    ManualPortfolioResponse, ManualPositionResponse, ManualTradeResponse,
)
from app.schemas.watchlist import WatchlistResponse
from app.schemas.backtest import (
    BacktestParams, BacktestRequest, BacktestResultResponse, BacktestResultDetailResponse,
)

__all__ = [
    "RegisterRequest", "LoginRequest", "AuthResponse", "UserResponse",
    "FundResponse", "FundNavResponse", "FundValuationResponse",
    "FundHoldingResponse", "FundManagerResponse", "IndexQuotaResponse",
    "SignalResponse",
    "AutoConfigResponse", "AutoPortfolioResponse", "AutoPositionResponse",
    "AutoTradeResponse", "AutoReportResponse",
    "ExecutionItemResponse", "ExecutionItemCreate", "ExecutionItemUpdate",
    "ManualPortfolioResponse", "ManualPositionResponse", "ManualTradeResponse",
    "WatchlistResponse",
    "BacktestParams", "BacktestRequest", "BacktestResultResponse", "BacktestResultDetailResponse",
]
