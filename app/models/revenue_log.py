"""
Revenue Log model for analytics
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from app.db.base_class import Base


class RevenueLog(Base):
    __tablename__ = "revenue_logs"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    amount = Column(Float, nullable=False)
    type = Column(String(50), nullable=False)  # "sale", "refund", "discount"
    description = Column(String(300), nullable=True)
    logged_at = Column(DateTime, default=datetime.utcnow, index=True)
