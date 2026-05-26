from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Text, Index, UniqueConstraint, func
from app.database import Base


class Signal(Base):
    __tablename__ = "signals"
    __table_args__ = (
        UniqueConstraint("fund_code", "date", name="uq_signal_code_date"),
        Index("ix_signal_date", "date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_code = Column(String(20), nullable=False, index=True)
    date = Column(Date, nullable=False)
    score = Column(Float, nullable=False)
    level = Column(String(1), nullable=False)  # S/A/B/C/D
    action = Column(String(10), nullable=False)  # buy/hold/sell
    factors_detail = Column(Text)  # JSON
    recommendation = Column(Text)  # JSON: {short, professional, plain}
    created_at = Column(DateTime, nullable=False, server_default=func.now())
