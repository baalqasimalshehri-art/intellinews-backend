"""Initialize default RSS feeds"""

from sqlalchemy import text
from app.database import engine


DEFAULT_FEEDS = [
    # Financial Feeds
    {
        "name": "Yahoo Finance",
        "url": "https://finance.yahoo.com/news/rssindex",
        "source_type": "financial"
    },
    {
        "name": "MarketWatch - Top Stories",
        "url": "https://www.marketwatch.com/rss/topstories",
        "source_type": "financial"
    },
    {
        "name": "Investing.com",
        "url": "https://www.investing.com/rss/news.rss",
        "source_type": "financial"
    },
    {
        "name": "Bloomberg Markets",
        "url": "https://feeds.bloomberg.com/markets/news.rss",
        "source_type": "financial"
    },
    {
        "name": "CNBC Top News",
        "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "source_type": "financial"
    },
    {
        "name": "Reuters Business",
        "url": "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best",
        "source_type": "financial"
    },
    {
        "name": "Financial Times",
        "url": "https://www.ft.com/?format=rss",
        "source_type": "financial"
    },
    {
        "name": "WSJ Markets",
        "url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
        "source_type": "financial"
    },
    # Academic Feeds
    {
        "name": "arXiv CS",
        "url": "http://export.arxiv.org/rss/cs",
        "source_type": "academic"
    },
    {
        "name": "arXiv AI",
        "url": "http://export.arxiv.org/rss/cs.AI",
        "source_type": "academic"
    },
    # Industry/Tech Feeds
    {
        "name": "TechCrunch",
        "url": "https://techcrunch.com/feed/",
        "source_type": "industry"
    },
    {
        "name": "VentureBeat",
        "url": "https://venturebeat.com/feed/",
        "source_type": "industry"
    },
    {
        "name": "The Verge",
        "url": "https://www.theverge.com/rss/index.xml",
        "source_type": "industry"
    }
]


def create_default_feeds():
    """Create default RSS feeds if they don't exist"""
    try:
        with engine.connect() as conn:
            for feed in DEFAULT_FEEDS:
                # Check if feed already exists
                result = conn.execute(
                    text("SELECT id FROM rss_feeds WHERE url = :url"),
                    {"url": feed["url"]}
                )
                existing = result.first()

                if not existing:
                    # Insert new feed
                    conn.execute(
                        text("""
                            INSERT INTO rss_feeds (name, url, source_type, is_active, created_at)
                            VALUES (:name, :url, :source_type, true, NOW())
                        """),
                        {
                            "name": feed["name"],
                            "url": feed["url"],
                            "source_type": feed["source_type"]
                        }
                    )
                    conn.commit()
                    print(f"✓ Added RSS feed: {feed['name']}")
                else:
                    print(f"  Feed already exists: {feed['name']}")

        print(f"\n✅ Default RSS feeds initialized successfully!")

    except Exception as e:
        print(f"⚠️  Error creating default feeds: {e}")


if __name__ == "__main__":
    create_default_feeds()
