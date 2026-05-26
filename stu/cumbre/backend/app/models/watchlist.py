from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint, func
from app.database import Base


class Watchlist(Base):
    __tablename__ = "watchlists"
    __table_args__ = (
        UniqueConstraint("user_id", "fund_code", name="uq_watchlist_user_fund"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    fund_code = Column(String(20), nullable=False)
    group_name = Column(String(100), nullable=False, default="默认")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
