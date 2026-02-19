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
    },
    {
        "name": "Wired",
        "url": "https://www.wired.com/feed/rss",
        "source_type": "industry"
    },
    {
        "name": "Ars Technica",
        "url": "https://feeds.arstechnica.com/arstechnica/index",
        "source_type": "industry"
    },
    {
        "name": "Hacker News Front Page",
        "url": "https://hnrss.org/frontpage",
        "source_type": "industry"
    },
    {
        "name": "MIT Technology Review",
        "url": "https://www.technologyreview.com/feed/",
        "source_type": "industry"
    },
    {
        "name": "ZDNet",
        "url": "https://www.zdnet.com/news/rss.xml",
        "source_type": "industry"
    },
    {
        "name": "Engadget",
        "url": "https://www.engadget.com/rss.xml",
        "source_type": "industry"
    },
    {
        "name": "Fast Company Tech",
        "url": "https://www.fastcompany.com/technology/rss",
        "source_type": "industry"
    },
    {
        "name": "SiliconANGLE",
        "url": "https://siliconangle.com/feed/",
        "source_type": "industry"
    },
    {
        "name": "InfoQ",
        "url": "https://feed.infoq.com",
        "source_type": "industry"
    },
    {
        "name": "Dev.to",
        "url": "https://dev.to/feed",
        "source_type": "industry"
    },
    # Additional Financial Feeds
    {
        "name": "Seeking Alpha",
        "url": "https://seekingalpha.com/feed.xml",
        "source_type": "financial"
    },
    {
        "name": "Benzinga",
        "url": "https://www.benzinga.com/feed",
        "source_type": "financial"
    },
    {
        "name": "Forbes Business",
        "url": "https://www.forbes.com/business/feed/",
        "source_type": "financial"
    },
    {
        "name": "Nasdaq News",
        "url": "https://www.nasdaq.com/feed/rssoutbound?category=Markets",
        "source_type": "financial"
    },
    {
        "name": "CoinDesk",
        "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "source_type": "financial"
    },
    {
        "name": "Investopedia News",
        "url": "https://www.investopedia.com/feedbuilder/feed/getfeed?feedName=rss_headline",
        "source_type": "financial"
    },
    {
        "name": "Business Insider Markets",
        "url": "https://markets.businessinsider.com/rss/news",
        "source_type": "financial"
    },
    {
        "name": "Motley Fool",
        "url": "https://www.fool.com/feeds/index.aspx",
        "source_type": "financial"
    },
    # Additional Academic Feeds
    {
        "name": "arXiv Machine Learning",
        "url": "http://export.arxiv.org/rss/cs.LG",
        "source_type": "academic"
    },
    {
        "name": "arXiv Data Science",
        "url": "http://export.arxiv.org/rss/stat.ML",
        "source_type": "academic"
    },
    {
        "name": "PLOS ONE",
        "url": "https://journals.plos.org/plosone/feed/atom",
        "source_type": "academic"
    },
    {
        "name": "Nature News",
        "url": "https://www.nature.com/nature.rss",
        "source_type": "academic"
    },
    # --- Additional Industry / Tech Feeds ---
    {
        "name": "TechRepublic",
        "url": "https://www.techrepublic.com/rssfeeds/articles/",
        "source_type": "industry"
    },
    {
        "name": "PCMag",
        "url": "https://www.pcmag.com/rss/news",
        "source_type": "industry"
    },
    {
        "name": "Gizmodo",
        "url": "https://gizmodo.com/rss",
        "source_type": "industry"
    },
    {
        "name": "9to5Mac",
        "url": "https://9to5mac.com/feed/",
        "source_type": "industry"
    },
    {
        "name": "9to5Google",
        "url": "https://9to5google.com/feed/",
        "source_type": "industry"
    },
    {
        "name": "Android Authority",
        "url": "https://www.androidauthority.com/feed/",
        "source_type": "industry"
    },
    {
        "name": "Tom's Hardware",
        "url": "https://www.tomshardware.com/feeds/all",
        "source_type": "industry"
    },
    {
        "name": "The Next Web",
        "url": "https://thenextweb.com/feed/",
        "source_type": "industry"
    },
    {
        "name": "Digital Trends",
        "url": "https://www.digitaltrends.com/feed/",
        "source_type": "industry"
    },
    {
        "name": "Slashdot",
        "url": "https://rss.slashdot.org/Slashdot/slashdotMain",
        "source_type": "industry"
    },
    {
        "name": "O'Reilly Radar",
        "url": "https://www.oreilly.com/radar/feed.xml",
        "source_type": "industry"
    },
    {
        "name": "GitHub Blog",
        "url": "https://github.blog/feed/",
        "source_type": "industry"
    },
    {
        "name": "Google AI Blog",
        "url": "https://blog.research.google/feeds/posts/default",
        "source_type": "industry"
    },
    {
        "name": "OpenAI Blog",
        "url": "https://openai.com/blog/rss.xml",
        "source_type": "industry"
    },
    {
        "name": "Netflix Tech Blog",
        "url": "https://netflixtechblog.com/feed",
        "source_type": "industry"
    },
    {
        "name": "AWS News Blog",
        "url": "https://aws.amazon.com/blogs/aws/feed/",
        "source_type": "industry"
    },
    {
        "name": "Towards Data Science",
        "url": "https://towardsdatascience.com/feed",
        "source_type": "industry"
    },
    {
        "name": "Smashing Magazine",
        "url": "https://www.smashingmagazine.com/feed/",
        "source_type": "industry"
    },
    # --- Additional Financial Feeds ---
    {
        "name": "Reuters Markets",
        "url": "https://feeds.reuters.com/reuters/businessNews",
        "source_type": "financial"
    },
    {
        "name": "AP Business",
        "url": "https://rsshub.app/apnews/topics/business-news",
        "source_type": "financial"
    },
    {
        "name": "The Economist Finance",
        "url": "https://www.economist.com/finance-and-economics/rss.xml",
        "source_type": "financial"
    },
    {
        "name": "Harvard Business Review",
        "url": "https://hbr.org/resources/rss/hbr-topic-rss.xml",
        "source_type": "financial"
    },
    {
        "name": "Inc. Magazine",
        "url": "https://www.inc.com/rss",
        "source_type": "financial"
    },
    {
        "name": "Entrepreneur",
        "url": "https://www.entrepreneur.com/latest.rss",
        "source_type": "financial"
    },
    {
        "name": "Bitcoin Magazine",
        "url": "https://bitcoinmagazine.com/.rss/full/",
        "source_type": "financial"
    },
    {
        "name": "Cointelegraph",
        "url": "https://cointelegraph.com/rss",
        "source_type": "financial"
    },
    {
        "name": "TechCrunch Startups",
        "url": "https://techcrunch.com/category/startups/feed/",
        "source_type": "financial"
    },
    # --- Additional Academic Feeds ---
    {
        "name": "arXiv Computation & Language",
        "url": "http://export.arxiv.org/rss/cs.CL",
        "source_type": "academic"
    },
    {
        "name": "arXiv Computer Vision",
        "url": "http://export.arxiv.org/rss/cs.CV",
        "source_type": "academic"
    },
    {
        "name": "arXiv Robotics",
        "url": "http://export.arxiv.org/rss/cs.RO",
        "source_type": "academic"
    },
    {
        "name": "arXiv Quantitative Finance",
        "url": "http://export.arxiv.org/rss/q-fin",
        "source_type": "academic"
    },
    {
        "name": "arXiv Cybersecurity",
        "url": "http://export.arxiv.org/rss/cs.CR",
        "source_type": "academic"
    },
    {
        "name": "Science Daily - Technology",
        "url": "https://www.sciencedaily.com/rss/computers_math/computer_science.xml",
        "source_type": "academic"
    },
    {
        "name": "Science Daily - AI",
        "url": "https://www.sciencedaily.com/rss/computers_math/artificial_intelligence.xml",
        "source_type": "academic"
    },
    {
        "name": "MIT News - AI",
        "url": "https://news.mit.edu/topic/mitartificial-intelligence2-rss.xml",
        "source_type": "academic"
    },
    {
        "name": "Stanford AI Lab Blog",
        "url": "https://ai.stanford.edu/blog/feed.xml",
        "source_type": "academic"
    },
    {
        "name": "DeepMind Blog",
        "url": "https://deepmind.google/blog/rss.xml",
        "source_type": "academic"
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
