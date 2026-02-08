from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from datetime import datetime, timedelta
from app.models.article import Article
from app.services.openai_service import openai_service
import numpy as np


class RetrievalService:
    """RAG-style retrieval system using pgvector for semantic search"""

    def __init__(self):
        self.openai_service = openai_service

    def semantic_search(
        self,
        db: Session,
        query_embedding: List[float],
        source_type: Optional[str] = None,
        limit: int = 50,
        min_date: Optional[datetime] = None
    ) -> List[Tuple[Article, float]]:
        """
        Perform semantic search using vector similarity

        Args:
            db: Database session
            query_embedding: Query vector embedding
            source_type: Filter by source type ("academic", "industry", "financial")
            limit: Maximum number of results
            min_date: Minimum publication date

        Returns:
            List of (Article, distance) tuples sorted by similarity
        """
        # Build query with filters
        query = db.query(Article).filter(Article.embedding.isnot(None))

        # Apply source type filter
        if source_type and source_type.lower() != "both":
            query = query.filter(Article.source_type == source_type.lower())

        # Apply date filter
        if min_date:
            query = query.filter(Article.published_date >= min_date)

        # Order by vector similarity (cosine distance)
        query = query.order_by(Article.embedding.cosine_distance(query_embedding))

        # Limit results
        query = query.limit(limit)

        # Execute and calculate similarity scores
        results = []
        for article in query.all():
            # Calculate cosine similarity (1 - distance)
            distance = self._cosine_distance(query_embedding, article.embedding)
            similarity = 1 - distance
            results.append((article, similarity))

        return results

    def search_by_user_preferences(
        self,
        db: Session,
        user_topics: List[str],
        user_keywords: List[str],
        source_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Tuple[Article, float]]:
        """
        Search articles based on user preferences

        Args:
            db: Database session
            user_topics: User's preferred topics
            user_keywords: User's preferred keywords
            source_type: Filter by source type
            limit: Maximum number of results

        Returns:
            List of (Article, similarity_score) tuples
        """
        # Generate query embedding from user preferences
        query_text = f"Topics: {', '.join(user_topics)}. Keywords: {', '.join(user_keywords)}."
        query_embedding = self.openai_service.generate_embedding(query_text)

        # Only show recent articles (2025+)
        min_date = datetime(2025, 1, 1)

        return self.semantic_search(
            db=db,
            query_embedding=query_embedding,
            source_type=source_type,
            limit=limit,
            min_date=min_date
        )

    def hybrid_ranking(
        self,
        articles_with_scores: List[Tuple[Article, float]],
        recency_weight: float = 0.3,
        relevance_weight: float = 0.7
    ) -> List[Tuple[Article, float, float, float]]:
        """
        Combine semantic similarity with recency for hybrid ranking

        Args:
            articles_with_scores: List of (Article, relevance_score) tuples
            recency_weight: Weight for freshness score (0.0 - 1.0)
            relevance_weight: Weight for relevance score (0.0 - 1.0)

        Returns:
            List of (Article, relevance_score, freshness_score, final_score) tuples
        """
        results = []

        for article, relevance_score in articles_with_scores:
            # Calculate freshness score
            freshness_score = self.calculate_freshness_score(article.published_date)

            # Calculate final score
            final_score = (
                relevance_weight * relevance_score +
                recency_weight * freshness_score
            )

            results.append((article, relevance_score, freshness_score, final_score))

        # Sort by final score (descending)
        results.sort(key=lambda x: x[3], reverse=True)

        return results

    @staticmethod
    def calculate_freshness_score(published_date: datetime) -> float:
        """
        Calculate freshness score based on article age

        Args:
            published_date: When the article was published

        Returns:
            Freshness score between 0.0 and 1.0
        """
        if not published_date:
            return 0.0

        days_old = (datetime.now() - published_date).days

        if days_old <= 7:
            return 1.0  # Last week
        elif days_old <= 30:
            return 0.8  # Last month
        elif days_old <= 90:
            return 0.6  # Last 3 months
        elif days_old <= 180:
            return 0.4  # Last 6 months
        else:
            return 0.2  # Older than 6 months

    @staticmethod
    def _cosine_distance(vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine distance between two vectors"""
        v1 = np.array(vec1)
        v2 = np.array(vec2)

        dot_product = np.dot(v1, v2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)

        if norm1 == 0 or norm2 == 0:
            return 1.0

        similarity = dot_product / (norm1 * norm2)
        distance = 1 - similarity

        return max(0.0, min(1.0, distance))


# Global instance
retrieval_service = RetrievalService()
