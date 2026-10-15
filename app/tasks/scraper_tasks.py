from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import SessionLocal
from app.models.article import Article
from app.models.settings import SystemSettings
from app.models.rss_feed import RSSFeed
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

        # Query active industry feeds from database
        industry_feeds_db = RSSFeed.get_active_feeds_by_type(db, "industry")
        if industry_feeds_db:
            industry_feed_urls = [feed.url for feed in industry_feeds_db]
            print(f"[Scheduler] Scraping {len(industry_feed_urls)} industry feeds from database")
            industry_articles = rss_scraper.scrape_multiple_feeds(industry_feed_urls, source_type="industry", limit=30)
            all_articles.extend(industry_articles)
            print(f"Found {len(industry_articles)} articles from industry sources")
        else:
            print("[Scheduler] No active industry feeds found in database")

        # Query active financial feeds from database
        financial_feeds_db = RSSFeed.get_active_feeds_by_type(db, "financial")
        if financial_feeds_db:
            financial_feed_urls = [feed.url for feed in financial_feeds_db]
            print(f"[Scheduler] Scraping {len(financial_feed_urls)} financial feeds from database")
            news_articles = rss_scraper.scrape_multiple_feeds(financial_feed_urls, source_type="financial", limit=30)
            all_articles.extend(news_articles)
            print(f"Found {len(news_articles)} articles from financial sources")
        else:
            print("[Scheduler] No active financial feeds found in database")

        # 4. Scrape custom RSS feeds from admin settings
        print("Checking for custom RSS feeds from admin settings...")
        custom_sources_setting = db.query(SystemSettings).filter(SystemSettings.key == "sources").first()
        if custom_sources_setting and custom_sources_setting.value:
            custom_feeds = custom_sources_setting.value
            if isinstance(custom_feeds, list) and len(custom_feeds) > 0:
                print(f"Scraping {len(custom_feeds)} custom RSS feeds...")
                custom_articles = rss_scraper.scrape_multiple_feeds(custom_feeds, source_type="industry", limit=30)
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
                    article_metadata=article_data.get("metadata", {})
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


def resummarize_empty_articles(batch_size: int = 200):
    """
    Find articles with empty summaries and regenerate them using the current GPT model.

    This runs:
    - Once at application startup (in a background thread)
    - Daily at 01:00 UTC via the scheduler

    Articles whose summary was cleared by the error-migration (or never generated)
    will be processed here so newsletters always have proper summaries.
    """
    print("=" * 60)
    print("[Resummarize] Starting re-summarization task...")
    print("=" * 60)
    db = SessionLocal()
    fixed = 0
    failed = 0

    try:
        # Count total articles with empty summaries (for progress reporting)
        total_empty = (
            db.query(Article)
            .filter(
                (Article.summary == None) | (Article.summary == "")
            )
            .count()
        )

        # Fetch the batch to process
        empty_articles = (
            db.query(Article)
            .filter(
                (Article.summary == None) | (Article.summary == "")
            )
            .limit(batch_size)
            .all()
        )

        print(f"[Resummarize] Total articles with empty summary in DB: {total_empty}")
        print(f"[Resummarize] Processing batch of {len(empty_articles)} articles now...")
        print("-" * 60)

        for idx, article in enumerate(empty_articles, 1):
            try:
                print(f"[Resummarize] [{idx}/{len(empty_articles)}] Summarising: \"{article.title[:70]}\"")

                summary_data = openai_service.summarize_article(
                    content=article.content,
                    source_type=article.source_type,
                    title=article.title,
                    timeout=60
                )

                generated_summary = summary_data.get("summary", "")
                key_points = summary_data.get("key_points", [])
                tags = summary_data.get("tags", [])

                # Only save if we got a real summary (not another error string)
                if generated_summary and not generated_summary.startswith("Error"):
                    article.summary = generated_summary
                    article.key_points = key_points
                    article.tags = tags
                    db.commit()
                    fixed += 1

                    # Log the full generated summary so it's visible in Railway logs
                    print(f"[Resummarize] ✓ Summary generated for article {article.id}:")
                    print(f"             TITLE   : {article.title[:80]}")
                    print(f"             SUMMARY : {generated_summary}")
                    print(f"             TAGS    : {', '.join(tags[:5])}")
                    print(f"             POINTS  : {len(key_points)} key points")
                    print("-" * 60)
                else:
                    failed += 1
                    print(f"[Resummarize] ✗ Empty/error summary returned for article {article.id} — skipping")
                    print("-" * 60)

            except Exception as e:
                print(f"[Resummarize] ✗ Exception for article {article.id} ({article.title[:50]}): {e}")
                failed += 1
                db.rollback()
                continue

        remaining = total_empty - fixed
        print("=" * 60)
        print(f"[Resummarize] DONE — {fixed} fixed, {failed} failed, {max(0, remaining)} still remaining in DB")
        if remaining > 0:
            print(f"[Resummarize] Remaining articles will be processed in the next daily run at 01:00 UTC")
        print("=" * 60)

    except Exception as e:
        print(f"[Resummarize] Fatal error: {e}")
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

    # Re-summarise any articles that still have empty summaries (runs daily at 01:00)
    scheduler.add_job(
        resummarize_empty_articles,
        'cron',
        hour=1,
        minute=0,
        id='daily_resummarize'
    )

    scheduler.start()
    print("Scheduler started. Articles will be scraped daily at midnight.")

    return scheduler


# For manual testing
if __name__ == "__main__":
    scrape_and_process_articles()
