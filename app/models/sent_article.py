from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base


class SentArticle(Base):
    """Tracks which articles have already been delivered to each user."""

    __tablename__ = "sent_articles"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    sent_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("article_id", "user_id", name="uq_sent_article_user"),
    )
