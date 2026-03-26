"""
Return Request schemas
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.enums import ReturnStatus


class ReturnCreate(BaseModel):
    order_id: int
    reason: str


class ReturnAdminUpdate(BaseModel):
    status: ReturnStatus
    admin_notes: Optional[str] = None
    refund_amount: Optional[float] = None


class ReturnResponse(BaseModel):
    id: int
    order_id: int
    user_id: int
    reason: str
    status: ReturnStatus
    refund_amount: Optional[float]
    admin_notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
