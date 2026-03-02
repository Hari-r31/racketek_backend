"""
HomepageContent model — stores all homepage sections as JSON in a single row.
Each section_key maps to one block of the homepage (banners, testimonials, etc.)
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import JSON
from app.db.base_class import Base


class HomepageContent(Base):
    __tablename__ = "homepage_content"

    id          = Column(Integer, primary_key=True, index=True)
    section_key = Column(String(100), unique=True, nullable=False, index=True)
    content     = Column(JSON, nullable=False, default=dict)
    is_active   = Column(Boolean, default=True)
    updated_by  = Column(Integer, nullable=True)          # user id who last updated
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at  = Column(DateTime, default=datetime.utcnow)
