from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Text, Index, UniqueConstraint, func
from app.database import Base


class Fund(Base):
    __tablename__ = "funds"

    code = Column(String(20), primary_key=True)
    name = Column(String(200), nullable=False)
    type = Column(String(50), nullable=False)
    company = Column(String(100))
    fund_size = Column(Float)
    risk_level = Column(String(20))
    manager_id = Column(String(50))
    established_date = Column(Date)
    is_priority = Column(Integer, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class FundNav(Base):
    __tablename__ = "fund_navs"
    __table_args__ = (
        UniqueConstraint("fund_code", "date", name="uq_fund_nav_code_date"),
        Index("ix_fund_nav_code_date", "fund_code", "date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_code = Column(String(20), nullable=False, index=True)
    date = Column(Date, nullable=False)
    nav = Column(Float, nullable=False)
    acc_nav = Column(Float, nullable=False)


class FundValuation(Base):
    __tablename__ = "fund_valuations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_code = Column(String(20), nullable=False, index=True)
    date = Column(Date, nullable=False)
    pe = Column(Float)
    pb = Column(Float)
    pe_percentile = Column(Float)
    pb_percentile = Column(Float)


class FundHolding(Base):
    __tablename__ = "fund_holdings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_code = Column(String(20), nullable=False, index=True)
    stock_code = Column(String(20))
    stock_name = Column(String(200))
    ratio = Column(Float)
    date = Column(Date, nullable=False)


class FundManager(Base):
    __tablename__ = "fund_managers"

    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    tenure = Column(String(100))
    fund_codes = Column(Text)  # JSON array


class IndexQuota(Base):
    __tablename__ = "index_quotas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    index_code = Column(String(20), nullable=False, index=True)
    name = Column(String(100))
    pe = Column(Float)
    pb = Column(Float)
    pe_percentile = Column(Float)
    pb_percentile = Column(Float)
    date = Column(Date, nullable=False)
