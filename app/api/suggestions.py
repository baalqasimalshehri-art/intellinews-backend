from typing import List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.suggestion_service import (
    get_suggested_keywords,
    get_trending_topics,
)

router = APIRouter(prefix="/api/suggestions", tags=["suggestions"])


class KeywordRequest(BaseModel):
    """Topics the user has selected, used to tailor keyword suggestions."""
    topics: List[str] = []
    source: str = "both"
    limit: int = 12


@router.get("/topics")
async def suggest_topics(
    source: str = Query("both", description="academic, industry, financial or both"),
    limit: int = Query(24, ge=4, le=40),
    db: Session = Depends(get_db),
):
    """
    Topics trending across recently scraped articles.

    Derived from tag frequency over the trend window, then cleaned up by GPT.
    Falls back to a static list if there is no recent data or AI is unavailable.
    """
    return get_trending_topics(db, source=source, limit=limit)


@router.post("/keywords")
async def suggest_keywords(
    payload: KeywordRequest,
    db: Session = Depends(get_db),
):
    """
    Keywords relevant to the topics the user has selected.

    Grounded in articles matching those topics so suggestions stay specific.
    """
    return get_suggested_keywords(
        db,
        topics=payload.topics,
        source=payload.source,
        limit=payload.limit,
    )
