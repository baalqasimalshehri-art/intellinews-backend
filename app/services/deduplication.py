from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.article import Article
from app.services.openai_service import openai_service
import numpy as np


class DeduplicationService:
    """Service for detecting and removing duplicate articles using embeddings"""

    def __init__(self, similarity_threshold: float = 0.95):
        """
        Initialize deduplication service

        Args:
            similarity_threshold: Cosine similarity threshold for considering articles as duplicates
                                 (0.95 = 95% similar)
        """
        self.similarity_threshold = similarity_threshold
        self.openai_service = openai_service

    def is_duplicate(
        self,
        db: Session,
        article_embedding: List[float],
        source_type: Optional[str] = None
    ) -> bool:
        """
        Check if an article is a duplicate based on embedding similarity

        Args:
            db: Database session
            article_embedding: Embedding vector of the article to check
            source_type: Optional filter by source type

        Returns:
            True if a similar article exists, False otherwise
        """
        # Query for similar articles using vector search
        query = db.query(Article).filter(Article.embedding.isnot(None))

        if source_type:
            query = query.filter(Article.source_type == source_type)

        # Order by cosine distance
        query = query.order_by(Article.embedding.cosine_distance(article_embedding))

        # Get the most similar article
        similar_article = query.first()

        if not similar_article:
            return False

        # Calculate similarity
        similarity = self._calculate_similarity(article_embedding, similar_article.embedding)

        # Check if similarity exceeds threshold
        return similarity >= self.similarity_threshold

    def find_duplicates_in_batch(
        self,
        db: Session,
        articles: List[dict]
    ) -> List[dict]:
        """
        Remove duplicates from a batch of articles before inserting

        Args:
            db: Database session
            articles: List of article dictionaries with embeddings

        Returns:
            List of unique articles (duplicates removed)
        """
        unique_articles = []

        for article in articles:
            # Check if article has embedding
            if "embedding" not in article or not article["embedding"]:
                # Generate embedding if missing
                content = f"{article.get('title', '')} {article.get('content', '')}"
                article["embedding"] = self.openai_service.generate_embedding(content)

            # Check for duplicates
            if not self.is_duplicate(db, article["embedding"], article.get("source_type")):
                unique_articles.append(article)
            else:
                print(f"Duplicate detected: {article.get('title', 'Unknown')}")

        return unique_articles

    def remove_duplicates_from_db(
        self,
        db: Session,
        dry_run: bool = True
    ) -> int:
        """
        Find and remove duplicate articles from the database

        Args:
            db: Database session
            dry_run: If True, only report duplicates without deleting

        Returns:
            Number of duplicates found/removed
        """
        all_articles = db.query(Article).filter(Article.embedding.isnot(None)).all()

        duplicates_found = 0
        seen_embeddings = {}

        for article in all_articles:
            is_dup = False

            # Compare with previously seen articles
            for seen_id, seen_embedding in seen_embeddings.items():
                similarity = self._calculate_similarity(article.embedding, seen_embedding)

                if similarity >= self.similarity_threshold:
                    print(f"Duplicate found: {article.title} (similar to article {seen_id})")
                    duplicates_found += 1
                    is_dup = True

                    if not dry_run:
                        db.delete(article)

                    break

            if not is_dup:
                seen_embeddings[article.id] = article.embedding

        if not dry_run:
            db.commit()

        return duplicates_found

    @staticmethod
    def _calculate_similarity(vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        v1 = np.array(vec1)
        v2 = np.array(vec2)

        dot_product = np.dot(v1, v2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = dot_product / (norm1 * norm2)
        return max(0.0, min(1.0, similarity))


# Global instance
deduplication_service = DeduplicationService(similarity_threshold=0.95)
