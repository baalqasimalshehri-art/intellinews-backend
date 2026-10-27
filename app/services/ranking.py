from typing import List, Dict, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime, timedelta
from app.models.article import Article
from app.models.ranking import Ranking
from app.models.user import User
from app.models.sent_article import SentArticle
from app.services.retrieval import retrieval_service
from app.services.openai_service import openai_service


class RankingService:
    """AI-driven ranking service with explainability and intelligent caching"""

    def __init__(self):
        self.retrieval_service = retrieval_service
        self.openai_service = openai_service
        # Cache TTL: 1 hour
        self.cache_ttl_hours = 1

    def rank_articles_for_user(
        self,
        db: Session,
        user_id: int,
        user_topics: List[str],
        user_keywords: List[str],
        source_type: str = "both",
        limit: int = 20,
        offset: int = 0,
        exclude_sent: bool = False
    ) -> List[Dict]:
        """
        Rank articles for a specific user with AI-generated reasoning and intelligent caching

        This method implements cost-saving optimizations:
        1. Checks for cached rankings first (saves OpenAI API calls)
        2. Only runs RAG on new articles
        3. Reuses existing rankings when available

        Args:
            db: Database session
            user_id: User ID
            user_topics: User's preferred topics
            user_keywords: User's preferred keywords
            source_type: Content source type filter
            limit: Maximum number of articles to return
            offset: Number of articles to skip (for pagination)

        Returns:
            List of ranked article dictionaries with scores and reasoning
        """
        print(f"[RankingService] Ranking articles for user {user_id}, offset={offset}, limit={limit}")

        # Cached batches are only safe for interactive discovery, not newsletters.
        # Newsletters must exclude previously sent articles.
        cached_results = None
        if not exclude_sent:
            cached_results = self._get_cached_results_batch(
                db=db,
                user_id=user_id,
                offset=offset,
                limit=limit,
                source_type=source_type
            )

        if cached_results and len(cached_results) >= limit:
            print(f"[RankingService] Using {len(cached_results)} cached rankings (cost savings!)")
            return cached_results[:limit]

        # No sufficient cache, run RAG retrieval
        print(f"[RankingService] Running RAG retrieval for new articles")

        # Fetch IDs of articles already delivered to this user (newsletter path only)
        sent_ids = []
        if exclude_sent:
            sent_ids = [
                r.article_id
                for r in db.query(SentArticle.article_id)
                .filter(SentArticle.user_id == user_id)
                .all()
            ]

        # Step 1: Retrieve relevant articles using RAG
        # Wider candidate pool for more variety (minimum 60)
        total_to_fetch = max((offset + limit) * 4, 60)
        articles_with_scores = self.retrieval_service.search_by_user_preferences(
            db=db,
            user_topics=user_topics,
            user_keywords=user_keywords,
            source_type=source_type,
            limit=total_to_fetch,
            excluded_article_ids=sent_ids if sent_ids else None
        )

        # Step 2: Apply hybrid ranking (semantic + recency)
        ranked_articles = self.retrieval_service.hybrid_ranking(
            articles_with_scores=articles_with_scores,
            recency_weight=0.3,
            relevance_weight=0.7
        )

        # Step 3: Apply offset and limit
        top_articles = ranked_articles[offset:offset + limit]

        # Step 4: Generate AI reasoning for each ranking (with caching)
        results = []
        for article, relevance_score, freshness_score, final_score in top_articles:
            # Check if we already have a cached ranking for this article + user
            cached_ranking = self._get_cached_ranking(
                db=db,
                article_id=article.id,
                user_id=user_id
            )

            if cached_ranking:
                # Reuse cached ranking (cost savings!)
                print(f"[RankingService] Using cached ranking for article {article.id}")
                reasoning = cached_ranking.reasoning
                # Use cached scores if they exist, otherwise use current ones
                relevance_score = cached_ranking.relevance_score
                freshness_score = cached_ranking.freshness_score
                final_score = cached_ranking.final_score
            else:
                # Generate new reasoning using GPT (only for new articles)
                print(f"[RankingService] Generating new ranking for article {article.id}")
                reasoning = self.openai_service.generate_ranking_reasoning(
                    article_title=article.title,
                    article_source=article.source,
                    source_type=article.source_type,
                    published_date=article.published_date.strftime("%Y-%m-%d"),
                    user_topics=user_topics,
                    user_keywords=user_keywords,
                    relevance_score=relevance_score,
                    freshness_score=freshness_score,
                    final_score=final_score
                )

                # Save new ranking to database for future use
                self._save_ranking(
                    db=db,
                    article_id=article.id,
                    user_id=user_id,
                    relevance_score=relevance_score,
                    freshness_score=freshness_score,
                    final_score=final_score,
                    reasoning=reasoning
                )

            # Build result dictionary
            result = {
                **article.to_dict(),
                "relevanceScore": round(relevance_score, 3),
                "freshnessScore": round(freshness_score, 3),
                "finalScore": round(final_score, 3),
                "reasoning": reasoning
            }

            results.append(result)

        return results

    def _get_cached_results_batch(
        self,
        db: Session,
        user_id: int,
        offset: int,
        limit: int,
        source_type: str = "both"
    ) -> Optional[List[Dict]]:
        """
        Get a batch of cached rankings for a user

        Args:
            db: Database session
            user_id: User ID
            offset: Skip this many results
            limit: Maximum results to return

        Returns:
            List of cached article dictionaries with rankings, or None if cache miss
        """
        # Get recent rankings (within cache TTL)
        cache_cutoff = self._cache_cutoff(db, user_id)

        rankings_query = db.query(Ranking).join(Article, Article.id == Ranking.article_id)\
            .filter(Ranking.user_id == user_id)\
            .filter(Ranking.created_at >= cache_cutoff)
        if source_type in ("academic", "industry", "financial"):
            rankings_query = rankings_query.filter(Article.source_type == source_type)
        rankings = rankings_query.order_by(Ranking.final_score.desc())\
            .offset(offset)\
            .limit(limit)\
            .all()

        if not rankings:
            return None

        # Build result dictionaries with article data
        results = []
        for ranking in rankings:
            article = db.query(Article).filter(Article.id == ranking.article_id).first()
            if article:
                result = {
                    **article.to_dict(),
                    "relevanceScore": round(ranking.relevance_score, 3),
                    "freshnessScore": round(ranking.freshness_score, 3),
                    "finalScore": round(ranking.final_score, 3),
                    "reasoning": ranking.reasoning
                }
                results.append(result)

        return results if results else None

    def _get_cached_ranking(
        self,
        db: Session,
        article_id: int,
        user_id: int
    ) -> Ranking:
        """
        Get cached ranking for article + user combination

        Args:
            db: Database session
            article_id: Article ID
            user_id: User ID

        Returns:
            Cached Ranking object or None if not found
        """
        cache_cutoff = self._cache_cutoff(db, user_id)

        return db.query(Ranking)\
            .filter(Ranking.article_id == article_id)\
            .filter(Ranking.user_id == user_id)\
            .filter(Ranking.created_at >= cache_cutoff)\
            .order_by(Ranking.created_at.desc())\
            .first()

    def _cache_cutoff(self, db: Session, user_id: int) -> datetime:
        """Invalidate old rankings whenever saved user preferences are updated.

        User.updated_at is updated by the existing preferences endpoint, so no
        schema migration or deletion of ranking history is required.
        """
        cutoff = datetime.utcnow() - timedelta(hours=self.cache_ttl_hours)
        updated_at = db.query(User.updated_at).filter(User.id == user_id).scalar()
        if updated_at is not None:
            cutoff = max(cutoff, updated_at)
        return cutoff

    def _save_ranking(
        self,
        db: Session,
        article_id: int,
        user_id: int,
        relevance_score: float,
        freshness_score: float,
        final_score: float,
        reasoning: str
    ):
        """Save ranking to database for analytics and future improvements"""
        ranking = Ranking(
            article_id=article_id,
            user_id=user_id,
            relevance_score=relevance_score,
            freshness_score=freshness_score,
            final_score=final_score,
            reasoning=reasoning
        )

        db.add(ranking)
        db.commit()

    def get_user_ranking_history(
        self,
        db: Session,
        user_id: int,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get user's ranking history for analytics

        Args:
            db: Database session
            user_id: User ID
            limit: Maximum number of rankings to return

        Returns:
            List of ranking dictionaries
        """
        rankings = db.query(Ranking)\
            .filter(Ranking.user_id == user_id)\
            .order_by(Ranking.created_at.desc())\
            .limit(limit)\
            .all()

        return [ranking.to_dict() for ranking in rankings]


# Global instance
ranking_service = RankingService()
