from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum
from sqlalchemy.sql import func
from app.database import Base
import enum


class SourceType(enum.Enum):
    """Source type enum"""
    academic = "academic"
    financial = "financial"
    industry = "industry"


class RSSFeed(Base):
    """RSS Feed model for managing news sources"""
    __tablename__ = "rss_feeds"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    url = Column(String, nullable=False, unique=True)
    source_type = Column(Enum(SourceType), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<RSSFeed(name='{self.name}', type='{self.source_type.value}')>"
