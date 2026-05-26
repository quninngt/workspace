from sqlalchemy import Column, Integer, String, Date, DateTime, Text, func
from app.database import Base


class BacktestResult(Base):
    __tablename__ = "backtest_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, default="")
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    params = Column(Text)  # JSON
    performance = Column(Text)  # JSON
    signal_distribution = Column(Text)  # JSON
    factor_contributions = Column(Text)  # JSON
    monthly_returns = Column(Text)  # JSON
    daily_values = Column(Text)  # JSON
    summary = Column(Text)  # JSON
    created_at = Column(DateTime, nullable=False, server_default=func.now())
