from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Text, UniqueConstraint, func
from app.database import Base


class AutoConfig(Base):
    __tablename__ = "auto_configs"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_auto_config_user"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    total_amount = Column(Float, nullable=False, default=0)
    daily_amount = Column(Float, nullable=False, default=0)
    plan_type = Column(String(10), nullable=False, default="daily")  # daily/weekly/monthly
    status = Column(String(20), nullable=False, default="active")
    last_executed_at = Column(Date)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class AutoPortfolio(Base):
    __tablename__ = "auto_portfolios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    cash = Column(Float, nullable=False, default=0)
    total_invested = Column(Float, nullable=False, default=0)
    market_value = Column(Float, nullable=False, default=0)
    nav_history = Column(Text)  # JSON
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class AutoPosition(Base):
    __tablename__ = "auto_positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(Integer, nullable=False, index=True)
    fund_code = Column(String(20), nullable=False)
    shares = Column(Float, nullable=False, default=0)
    cost_nav = Column(Float, nullable=False, default=0)
    allocation_ratio = Column(Float, nullable=False, default=0)


class AutoTrade(Base):
    __tablename__ = "auto_trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(Integer, nullable=False, index=True)
    fund_code = Column(String(20), nullable=False)
    type = Column(String(10), nullable=False)  # buy/sell
    amount = Column(Float, nullable=False)
    shares = Column(Float, nullable=False)
    nav = Column(Float, nullable=False)
    date = Column(Date, nullable=False)
    plan_type = Column(String(10), nullable=False)  # daily/weekly/monthly
    signal_id = Column(Integer)


class AutoReport(Base):
    __tablename__ = "auto_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    period_type = Column(String(10), nullable=False)  # weekly/monthly/quarterly
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    stats = Column(Text)  # JSON
    created_at = Column(DateTime, nullable=False, server_default=func.now())
