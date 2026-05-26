from app.models.user import User
from app.models.fund import Fund, FundNav, FundValuation, FundHolding, FundManager, IndexQuota
from app.models.signal import Signal
from app.models.auto import AutoConfig, AutoPortfolio, AutoPosition, AutoTrade, AutoReport
from app.models.manual import ExecutionItem, ManualPortfolio, ManualPosition, ManualTrade
from app.models.watchlist import Watchlist
from app.models.backtest import BacktestResult

all_models = [
    User,
    Fund, FundNav, FundValuation, FundHolding, FundManager, IndexQuota,
    Signal,
    AutoConfig, AutoPortfolio, AutoPosition, AutoTrade, AutoReport,
    ExecutionItem, ManualPortfolio, ManualPosition, ManualTrade,
    Watchlist,
    BacktestResult,
]
