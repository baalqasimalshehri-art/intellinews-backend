from sqlalchemy import Column, Integer, Float, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class Ranking(Base):
    """Ranking model to store AI-driven article rankings with explainability"""

    __tablename__ = "rankings"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Scoring components
    relevance_score = Column(Float, nullable=False)  # Semantic similarity to user preferences
    freshness_score = Column(Float, nullable=False)  # Recency score (0.0 - 1.0)
    final_score = Column(Float, nullable=False, index=True)  # Combined score

    # AI-generated explanation for why this article was ranked
    reasoning = Column(Text)

    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<Ranking(article_id={self.article_id}, user_id={self.user_id}, score={self.final_score})>"

    def to_dict(self):
        """Convert ranking to dictionary for API responses"""
        return {
            "id": self.id,
            "articleId": self.article_id,
            "userId": self.user_id,
            "relevanceScore": round(self.relevance_score, 3),
            "freshnessScore": round(self.freshness_score, 3),
            "finalScore": round(self.final_score, 3),
            "reasoning": self.reasoning,
            "createdAt": self.created_at.isoformat() if self.created_at else None
        }
