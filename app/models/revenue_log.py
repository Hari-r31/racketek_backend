"""
Revenue Log model for analytics

Enum source: app.enums.RevenueLogType  (do not redefine locally)
type column: String(50) — values must be one of RevenueLogType ("sale", "refund", "discount").
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from app.db.base_class import Base
from app.enums import RevenueLogType  # noqa: F401 — re-exported for import compatibility


class RevenueLog(Base):
    __tablename__ = "revenue_logs"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    amount = Column(Float, nullable=False)
    type = Column(String(50), nullable=False)  # RevenueLogType value: "sale" | "refund" | "discount"
    description = Column(String(300), nullable=True)
    logged_at = Column(DateTime, default=datetime.utcnow, index=True)
