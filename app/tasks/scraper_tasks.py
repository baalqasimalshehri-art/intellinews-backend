from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import SessionLocal
from app.models.article import Article
from app.models.settings import SystemSettings
from app.scrapers.arxiv_scraper import ArxivScraper, ARXIV_CATEGORIES
from app.scrapers.rss_scraper import RSSFeedScraper, RSS_FEEDS
from app.services.openai_service import openai_service
from app.services.deduplication import deduplication_service


def scrape_and_process_articles():
    """
    Main task to scrape articles from all sources, process them, and store in DB

    This task:
    1. Scrapes academic sources (arXiv)
    2. Scrapes industry sources via RSS feeds (TechCrunch, HackerNews, etc.)
    3. Scrapes financial sources via RSS feeds (Reuters, BBC, etc.)
    4. Generates embeddings for each article
    5. Generates AI summaries using context-aware prompts
    6. Removes duplicates using embedding similarity
    7. Stores unique articles in the database
    """
    print(f"[{datetime.now()}] Starting article scraping task...")

    db = SessionLocal()

    try:
        all_articles = []

        # 1. Scrape academic sources (arXiv)
        print("Scraping arXiv...")
        arxiv_scraper = ArxivScraper()

        # Scrape AI-related papers
        ai_papers = arxiv_scraper.scrape_by_categories(ARXIV_CATEGORIES["ai"])
        all_articles.extend(ai_papers)
        print(f"Found {len(ai_papers)} AI papers from arXiv")

        # 2. Scrape industry sources using RSS feeds
        print("Scraping industry sources with RSS feeds...")
        rss_scraper = RSSFeedScraper()

        # Scrape all predefined RSS feeds
        industry_feeds = [
            RSS_FEEDS["techcrunch"],
            RSS_FEEDS["venturebeat"],
            RSS_FEEDS["wired"],
            RSS_FEEDS["theverge"],
            RSS_FEEDS["arstechnica"],
            RSS_FEEDS["hackernews"],
            RSS_FEEDS["mit_tech_review"],
        ]

        industry_articles = rss_scraper.scrape_multiple_feeds(industry_feeds, source_type="industry", limit=10)
        all_articles.extend(industry_articles)
        print(f"Found {len(industry_articles)} articles from industry sources")

        # 3. Scrape tech/news sources using RSS feeds
        print("Scraping news sources with RSS feeds...")

        news_feeds = [
            RSS_FEEDS["reuters_tech"],
            RSS_FEEDS["bbc_tech"],
        ]

        news_articles = rss_scraper.scrape_multiple_feeds(news_feeds, source_type="financial", limit=10)
        all_articles.extend(news_articles)
        print(f"Found {len(news_articles)} articles from news sources")

        # 4. Scrape custom RSS feeds from admin settings
        print("Checking for custom RSS feeds from admin settings...")
        custom_sources_setting = db.query(SystemSettings).filter(SystemSettings.key == "sources").first()
        if custom_sources_setting and custom_sources_setting.value:
            custom_feeds = custom_sources_setting.value
            if isinstance(custom_feeds, list) and len(custom_feeds) > 0:
                print(f"Scraping {len(custom_feeds)} custom RSS feeds...")
                custom_articles = rss_scraper.scrape_multiple_feeds(custom_feeds, source_type="industry", limit=10)
                all_articles.extend(custom_articles)
                print(f"Found {len(custom_articles)} articles from custom feeds")

        print(f"Total articles scraped: {len(all_articles)}")

        # 4. Process each article
        print("Processing articles...")
        processed_count = 0

        for article_data in all_articles:
            try:
                # Check if article already exists (by URL)
                existing = db.query(Article).filter(Article.url == article_data["url"]).first()
                if existing:
                    continue

                # Generate embedding
                content_for_embedding = f"{article_data['title']} {article_data['content']}"
                embedding = openai_service.generate_embedding(content_for_embedding)
                article_data["embedding"] = embedding

                # Check for duplicates using embedding similarity
                if deduplication_service.is_duplicate(db, embedding, article_data["source_type"]):
                    print(f"Skipping duplicate: {article_data['title']}")
                    continue

                # Generate AI summary with context-aware prompts
                summary_data = openai_service.summarize_article(
                    content=article_data["content"],
                    source_type=article_data["source_type"],
                    title=article_data["title"]
                )

                # Create article object
                article = Article(
                    title=article_data["title"],
                    content=article_data["content"],
                    url=article_data["url"],
                    source=article_data["source"],
                    source_type=article_data["source_type"],
                    published_date=article_data["published_date"],
                    embedding=embedding,
                    summary=summary_data["summary"],
                    key_points=summary_data["key_points"],
                    tags=summary_data["tags"],
                    metadata=article_data.get("metadata", {})
                )

                db.add(article)
                processed_count += 1

                # Commit in batches
                if processed_count % 10 == 0:
                    db.commit()
                    print(f"Processed {processed_count} articles...")

            except Exception as e:
                print(f"Error processing article: {e}")
                continue

        # Final commit
        db.commit()
        print(f"Successfully processed and stored {processed_count} unique articles")

    except Exception as e:
        print(f"Error in scraping task: {e}")
        db.rollback()

    finally:
        db.close()


def start_scheduler():
    """
    Start background scheduler for automated scraping

    Schedule:
    - Daily at midnight: Scrape all sources
    """
    scheduler = BackgroundScheduler()

    # Schedule daily scraping at midnight
    scheduler.add_job(
        scrape_and_process_articles,
        'cron',
        hour=0,
        minute=0,
        id='daily_scraping'
    )

    scheduler.start()
    print("Scheduler started. Articles will be scraped daily at midnight.")

    return scheduler


# For manual testing
if __name__ == "__main__":
    scrape_and_process_articles()
