from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from app.database import get_db
from app.models.article import Article
from app.services.ranking import ranking_service
from app.services.openai_service import openai_service
from app.utils.cache import stats_cache, articles_cache, generate_cache_key

router = APIRouter(prefix="/api/articles", tags=["articles"])


class DiscoverRequest(BaseModel):
    """Request model for discovering articles"""
    userId: int
    topics: List[str]
    keywords: List[str]
    sourceType: str = "both"  # "academic", "industry", "financial", "both"
    limit: int = 20
    offset: int = 0


class ArticleResponse(BaseModel):
    """Response model for article with AI ranking"""
    id: int
    title: str
    summary: str
    keyPoints: List[str]
    tags: List[str]
    url: str
    source: str
    sourceType: str
    publishedDate: str
    relevanceScore: float
    freshnessScore: float
    finalScore: float
    reasoning: str


@router.post("/discover", response_model=List[ArticleResponse])
async def discover_articles(
    request: DiscoverRequest,
    db: Session = Depends(get_db)
):
    """
    Discover and rank articles for a user using AI-driven intelligence

    This endpoint:
    1. Uses RAG to retrieve semantically similar articles
    2. Filters by recency (2025+ only)
    3. Ranks using hybrid scoring (relevance + freshness)
    4. Generates AI explanations for each ranking
    """
    try:
        # Rank articles for the user
        ranked_articles = ranking_service.rank_articles_for_user(
            db=db,
            user_id=request.userId,
            user_topics=request.topics,
            user_keywords=request.keywords,
            source_type=request.sourceType,
            limit=request.limit,
            offset=request.offset
        )

        return ranked_articles

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error discovering articles: {str(e)}")


@router.get("/{article_id}")
async def get_article(
    article_id: int,
    db: Session = Depends(get_db)
):
    """Get a single article by ID"""
    article = db.query(Article).filter(Article.id == article_id).first()

    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    return article.to_dict()


@router.get("/")
async def list_articles(
    source_type: Optional[str] = Query(None, description="Filter by source type"),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """List articles with optional filtering"""
    query = db.query(Article)

    if source_type:
        query = query.filter(Article.source_type == source_type.lower())

    query = query.order_by(Article.published_date.desc())
    query = query.offset(offset).limit(limit)

    articles = query.all()

    return {
        "articles": [article.to_dict() for article in articles],
        "total": query.count(),
        "offset": offset,
        "limit": limit
    }


@router.get("/stats/summary")
async def get_article_stats(db: Session = Depends(get_db)):
    """Get statistics about articles in the database (cached for 5 minutes)"""
    from sqlalchemy import func
    from datetime import datetime, timedelta

    # Check cache first
    cache_key = "stats:summary"
    if cache_key in stats_cache:
        print(f"[Cache] HIT: stats - summary")
        return stats_cache[cache_key]

    print(f"[Cache] MISS: stats - summary")

    # Execute optimized queries using single query with conditional aggregation
    result = db.query(
        func.count(Article.id).label('total'),
        func.count().filter(Article.source_type == 'academic').label('academic'),
        func.count().filter(Article.source_type == 'industry').label('industry'),
        func.count().filter(Article.source_type == 'financial').label('financial'),
        func.avg(func.length(Article.summary)).label('avg_length')
    ).first()

    # Calculate time-based counts
    now = datetime.utcnow()
    last_24h = now - timedelta(hours=24)
    last_week = now - timedelta(days=7)

    articles_last_24h = db.query(func.count(Article.id))\
        .filter(Article.published_date >= last_24h).scalar() or 0

    articles_last_week = db.query(func.count(Article.id))\
        .filter(Article.published_date >= last_week).scalar() or 0

    response = {
        "total_articles": result.total or 0,
        "by_source_type": {
            "academic": result.academic or 0,
            "industry": result.industry or 0,
            "financial": result.financial or 0
        },
        "articles_last_24h": articles_last_24h,
        "articles_last_week": articles_last_week,
        "avg_summary_length": int(result.avg_length or 0)
    }

    # Store in cache
    stats_cache[cache_key] = response
    return response
