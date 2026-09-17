"""
AI-Driven Topic & Keyword Suggestion Service

Replaces the previously hardcoded topic/keyword lists with suggestions that are
derived from the articles actually being scraped, so they track current trends.

Two-stage approach:
  1. Mine recently scraped articles for their AI-generated tags and titles.
     Tag frequency across the last N days is a real trend signal.
  2. Ask GPT to turn that raw signal into clean, human-readable labels.

If either stage fails the service falls back to a static list, so the UI always
has something to render.
"""

import json
from collections import Counter
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from cachetools import TTLCache
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.article import Article
from app.services.openai_service import openai_service

# Cache AI results so the Preferences page doesn't hit OpenAI on every load.
_topic_cache = TTLCache(maxsize=32, ttl=6 * 60 * 60)      # 6 hours
_keyword_cache = TTLCache(maxsize=256, ttl=60 * 60)       # 1 hour

# How far back to look when measuring "current" trends.
TREND_WINDOW_DAYS = 14

# Source types understood by the Article model. "both" means all of them.
VALID_SOURCES = ("academic", "industry", "financial", "both")


# --- Static fallbacks -------------------------------------------------------
# Used only when the database has no recent articles or OpenAI is unavailable.

FALLBACK_TOPICS: Dict[str, List[str]] = {
    "academic": [
        "Machine Learning", "Quantum Computing", "Computational Biology",
        "Theoretical Physics", "Neuroscience", "Climate Science",
        "Materials Science", "Cryptography", "Computer Vision",
        "Natural Language Processing",
    ],
    "industry": [
        "Artificial Intelligence", "Cloud Computing", "Software Engineering",
        "Cybersecurity", "Data Science", "DevOps", "Mobile Development",
        "Web3", "IoT", "Edge Computing",
    ],
    "financial": [
        "Stock Markets", "Cryptocurrency", "FinTech", "Investment Banking",
        "DeFi", "Commodities", "Foreign Exchange", "Economic Policy",
        "Real Estate", "Venture Capital",
    ],
}

FALLBACK_KEYWORDS: Dict[str, List[str]] = {
    "academic": [
        "Peer Review", "Research Papers", "Clinical Trials", "Methodology",
        "Conference Proceedings", "Meta-Analysis", "Hypothesis Testing",
        "Literature Review",
    ],
    "industry": [
        "LLMs", "Neural Networks", "Microservices", "Kubernetes",
        "Zero Trust", "API Design", "DevSecOps", "CI/CD",
    ],
    "financial": [
        "Inflation", "Interest Rates", "IPO", "Earnings Report",
        "Market Volatility", "Portfolio Management", "Risk Assessment",
        "Gold Prices",
    ],
}


def _fallback_for(source: str, table: Dict[str, List[str]]) -> List[str]:
    """Combine every category for 'both', otherwise return that category."""
    if source == "both":
        merged: List[str] = []
        for values in table.values():
            for value in values:
                if value not in merged:
                    merged.append(value)
        return merged
    return list(table.get(source, table["industry"]))


# --- Trend mining -----------------------------------------------------------

def _recent_articles(db: Session, source: str, limit: int = 400) -> List[Article]:
    """Fetch recently published articles for a source type."""
    cutoff = datetime.utcnow() - timedelta(days=TREND_WINDOW_DAYS)
    query = db.query(Article).filter(Article.published_date >= cutoff)
    if source != "both":
        query = query.filter(Article.source_type == source)
    return query.order_by(Article.published_date.desc()).limit(limit).all()


def _tag_frequencies(articles: List[Article]) -> List[tuple]:
    """Count how often each AI-generated tag appears. This is the trend signal."""
    counter: Counter = Counter()
    for article in articles:
        for tag in (article.tags or []):
            cleaned = str(tag).strip()
            if cleaned:
                counter[cleaned.title()] += 1
    return counter.most_common(60)


def _ask_gpt(prompt: str, system: str, timeout: int = 30) -> Optional[dict]:
    """Call GPT with the same model-fallback behaviour as the rest of the app."""
    client = openai_service.client
    for model in [openai_service.gpt_model, openai_service.FALLBACK_MODEL]:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=700,
                temperature=0.4,
                response_format={"type": "json_object"},
                timeout=timeout,
            )
            if model != openai_service.gpt_model:
                print(f"[Suggestions] Used fallback model {model}")
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"[Suggestions] GPT error with model={model}: {e}")
            if model == openai_service.FALLBACK_MODEL:
                return None
            continue
    return None


# --- Public API -------------------------------------------------------------

def get_trending_topics(db: Session, source: str = "both", limit: int = 24) -> Dict:
    """
    Return topics trending across recently scraped articles for this source.

    Returns a dict with the topic list plus metadata describing how it was
    produced, so the UI can show whether results are live or a fallback.
    """
    source = source if source in VALID_SOURCES else "both"
    cache_key = f"topics:{source}:{limit}"
    if cache_key in _topic_cache:
        return _topic_cache[cache_key]

    articles = _recent_articles(db, source)
    trending_tags = _tag_frequencies(articles)

    result: Dict
    if not trending_tags:
        result = {
            "topics": _fallback_for(source, FALLBACK_TOPICS)[:limit],
            "source": source,
            "generated": False,
            "reason": "no recent articles to analyse",
            "articlesAnalysed": len(articles),
        }
        _topic_cache[cache_key] = result
        return result

    tag_summary = ", ".join(f"{tag} ({count})" for tag, count in trending_tags[:45])
    sample_titles = " | ".join((a.title or "")[:90] for a in articles[:25])

    prompt = (
        f"Below is real data from a news aggregator covering '{source}' sources "
        f"over the last {TREND_WINDOW_DAYS} days.\n\n"
        f"Most frequent tags (with occurrence counts):\n{tag_summary}\n\n"
        f"Sample recent headlines:\n{sample_titles}\n\n"
        f"From this data, produce exactly {limit} topic labels a reader would "
        f"choose to follow. Requirements:\n"
        f"- Reflect what is actually trending in the data above\n"
        f"- 1-3 words each, Title Case, no hashtags or punctuation\n"
        f"- Broad enough to be a subscribe-able interest, not a single news event\n"
        f"- No duplicates or near-duplicates\n"
        f'Respond as JSON: {{"topics": ["...", "..."]}}'
    )

    parsed = _ask_gpt(
        prompt,
        system="You identify trending subject areas from news data. Respond only with JSON.",
    )

    if not parsed or not isinstance(parsed.get("topics"), list):
        result = {
            "topics": _fallback_for(source, FALLBACK_TOPICS)[:limit],
            "source": source,
            "generated": False,
            "reason": "AI unavailable",
            "articlesAnalysed": len(articles),
        }
        _topic_cache[cache_key] = result
        return result

    topics: List[str] = []
    for item in parsed["topics"]:
        label = str(item).strip()
        if label and label.lower() not in {t.lower() for t in topics}:
            topics.append(label)

    result = {
        "topics": topics[:limit],
        "source": source,
        "generated": True,
        "articlesAnalysed": len(articles),
        "trendWindowDays": TREND_WINDOW_DAYS,
    }
    _topic_cache[cache_key] = result
    return result


def get_suggested_keywords(
    db: Session,
    topics: List[str],
    source: str = "both",
    limit: int = 12,
) -> Dict:
    """
    Suggest keywords relevant to the topics the user just selected.

    Grounded in articles that actually match those topics, so suggestions stay
    specific and current rather than generic.
    """
    source = source if source in VALID_SOURCES else "both"
    cleaned_topics = [str(t).strip() for t in (topics or []) if str(t).strip()]

    if not cleaned_topics:
        return {
            "keywords": _fallback_for(source, FALLBACK_KEYWORDS)[:limit],
            "topics": [],
            "generated": False,
            "reason": "no topics selected",
        }

    cache_key = f"kw:{source}:{limit}:" + "|".join(sorted(t.lower() for t in cleaned_topics))
    if cache_key in _keyword_cache:
        return _keyword_cache[cache_key]

    # Find articles that actually relate to the chosen topics.
    articles = _recent_articles(db, source, limit=600)
    lowered = [t.lower() for t in cleaned_topics]
    matched = []
    for article in articles:
        haystack = f"{article.title or ''} {' '.join(str(t) for t in (article.tags or []))}".lower()
        if any(topic in haystack for topic in lowered):
            matched.append(article)

    evidence = ""
    if matched:
        tags = _tag_frequencies(matched)
        tag_summary = ", ".join(f"{tag} ({count})" for tag, count in tags[:35])
        titles = " | ".join((a.title or "")[:90] for a in matched[:20])
        evidence = (
            f"\nTags on matching articles:\n{tag_summary}\n\n"
            f"Matching headlines:\n{titles}\n"
        )

    prompt = (
        f"A user follows these topics: {', '.join(cleaned_topics)}.\n"
        f"{evidence}\n"
        f"Suggest exactly {limit} keywords they should track to get more precise "
        f"coverage of those topics. Requirements:\n"
        f"- More specific than the topics themselves (techniques, technologies, "
        f"metrics, events, named concepts)\n"
        f"- 1-3 words each, Title Case, no hashtags\n"
        f"- Prefer terms that appear in the data above when it is provided\n"
        f"- Do not simply repeat the topic names\n"
        f'Respond as JSON: {{"keywords": ["...", "..."]}}'
    )

    parsed = _ask_gpt(
        prompt,
        system="You suggest precise tracking keywords for news topics. Respond only with JSON.",
    )

    if not parsed or not isinstance(parsed.get("keywords"), list):
        result = {
            "keywords": _fallback_for(source, FALLBACK_KEYWORDS)[:limit],
            "topics": cleaned_topics,
            "generated": False,
            "reason": "AI unavailable",
        }
        _keyword_cache[cache_key] = result
        return result

    seen = {t.lower() for t in cleaned_topics}
    keywords: List[str] = []
    for item in parsed["keywords"]:
        label = str(item).strip()
        if label and label.lower() not in seen:
            seen.add(label.lower())
            keywords.append(label)

    result = {
        "keywords": keywords[:limit],
        "topics": cleaned_topics,
        "generated": True,
        "articlesMatched": len(matched),
    }
    _keyword_cache[cache_key] = result
    return result
