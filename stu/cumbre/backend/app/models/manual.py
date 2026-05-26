from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Text, func
from app.database import Base


class ExecutionItem(Base):
    __tablename__ = "execution_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    plan_type = Column(String(10), nullable=False)  # daily/weekly/monthly
    fund_code = Column(String(20), nullable=False)
    action = Column(String(10), nullable=False)  # buy/sell/hold
    suggested_amount_min = Column(Float)
    suggested_amount_max = Column(Float)
    signal_id = Column(Integer)
    status = Column(String(20), nullable=False, default="pending")  # pending/executed/skipped
    date = Column(Date, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class ManualPortfolio(Base):
    __tablename__ = "manual_portfolios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String(100), nullable=False, default="默认组合")
    cash = Column(Float, nullable=False, default=0)
    total_invested = Column(Float, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class ManualPosition(Base):
    __tablename__ = "manual_positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(Integer, nullable=False, index=True)
    fund_code = Column(String(20), nullable=False)
    shares = Column(Float, nullable=False, default=0)
    cost_nav = Column(Float, nullable=False, default=0)


class ManualTrade(Base):
    __tablename__ = "manual_trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(Integer, nullable=False, index=True)
    fund_code = Column(String(20), nullable=False)
    type = Column(String(10), nullable=False)  # buy/sell
    amount = Column(Float, nullable=False)
    shares = Column(Float, nullable=False)
    nav = Column(Float, nullable=False)
    date = Column(Date, nullable=False)
    execution_id = Column(Integer)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
