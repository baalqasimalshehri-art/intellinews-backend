"""
User-Preference-Based Dynamic Article Scraping Service

This service scrapes articles dynamically based on individual user preferences,
ensuring each user gets fresh, personalized content tailored to their topics and interests.
"""

from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Dict, Optional
from app.models.article import Article
from app.models.user import User
from app.models.scraping_job import ScrapingJob
from app.models.rss_feed import RSSFeed
from app.scrapers.arxiv_scraper import ArxivScraper, ARXIV_CATEGORIES
from app.scrapers.rss_scraper import RSSFeedScraper, RSS_FEEDS
from app.services.openai_service import openai_service
from app.services.deduplication import deduplication_service
from app.database import SessionLocal


# Synonym map for topic expansion — used to match articles that use related terminology
TOPIC_SYNONYMS = {
    "ai": ["ai", "artificial intelligence", "machine learning", "deep learning", "neural", "llm", "gpt", "nlp", "ml", "generative"],
    "artificial intelligence": ["ai", "artificial intelligence", "machine learning", "deep learning", "neural", "llm", "gpt", "nlp"],
    "machine learning": ["machine learning", "ml", "deep learning", "neural network", "ai", "model training", "dataset"],
    "technology": ["technology", "tech", "software", "digital", "computing", "innovation", "startup", "app", "platform"],
    "finance": ["finance", "financial", "investment", "stock", "market", "economy", "banking", "trading", "portfolio", "fund"],
    "healthcare": ["healthcare", "health", "medical", "medicine", "clinical", "patient", "hospital", "drug", "pharma", "biotech"],
    "cybersecurity": ["cybersecurity", "security", "cyber", "hacker", "breach", "vulnerability", "malware", "threat", "privacy"],
    "blockchain": ["blockchain", "crypto", "cryptocurrency", "bitcoin", "ethereum", "defi", "web3", "nft", "token"],
    "data science": ["data science", "data", "analytics", "statistics", "python", "pandas", "visualization", "big data"],
    "cloud": ["cloud", "aws", "azure", "google cloud", "saas", "kubernetes", "devops", "infrastructure", "serverless"],
    "robotics": ["robotics", "robot", "automation", "autonomous", "drone", "manufacturing", "industrial"],
    "climate": ["climate", "environment", "sustainability", "carbon", "green", "renewable", "energy", "emissions"],
    "space": ["space", "nasa", "rocket", "satellite", "astronomy", "mars", "orbit", "spacecraft"],
    "quantum": ["quantum", "qubit", "quantum computing", "quantum mechanics", "quantum cryptography"],
    "startup": ["startup", "venture", "funding", "vc", "founder", "entrepreneur", "seed", "series a"],
    "biotech": ["biotech", "biotechnology", "gene", "genomics", "crispr", "protein", "biology", "drug"],
    "ecommerce": ["ecommerce", "e-commerce", "retail", "marketplace", "amazon", "shopify", "online shopping"],
    "social media": ["social media", "twitter", "facebook", "instagram", "tiktok", "youtube", "influencer"],
    "education": ["education", "edtech", "learning", "university", "school", "course", "online learning"],
}


class UserScraperService:
    """
    Service for scraping articles based on user preferences

    Dynamically scrapes and processes articles tailored to each user's:
    - Topics of interest
    - Keywords
    - Source preferences (academic, industry, financial)
    """

    def __init__(self):
        self.arxiv_scraper = ArxivScraper()
        self.rss_scraper = RSSFeedScraper()

    def scrape_for_user(
        self,
        db: Session,
        user_id: int,
        max_articles_per_source: int = 10
    ) -> Dict[str, any]:
        """
        Scrape articles based on a specific user's preferences

        Args:
            db: Database session
            user_id: User ID
            max_articles_per_source: Maximum articles to scrape per source

        Returns:
            Dictionary with scraping results and statistics
        """
        # Get user and preferences
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            raise ValueError(f"User {user_id} not found")

        prefs = user.preferences or {}
        topics = prefs.get("topics", [])
        keywords = prefs.get("keywords", [])
        source_pref = prefs.get("source", "both")

        if not topics:
            return {
                "success": False,
                "message": "User has no topics set. Please set preferences first.",
                "articles_scraped": 0,
                "articles_saved": 0
            }

        print(f"[UserScraper] Scraping for user {user_id} with topics: {topics}")

        all_articles = []
        stats = {
            "academic": 0,
            "industry": 0,
            "financial": 0
        }

        # Scrape based on source preference
        if source_pref in ["academic", "both"]:
            academic_articles = self._scrape_academic(topics, keywords, max_articles_per_source)
            all_articles.extend(academic_articles)
            stats["academic"] = len(academic_articles)
            print(f"[UserScraper] Found {len(academic_articles)} academic articles")

        if source_pref in ["industry", "both"]:
            industry_articles = self._scrape_industry(topics, keywords, max_articles_per_source)
            all_articles.extend(industry_articles)
            stats["industry"] = len(industry_articles)
            print(f"[UserScraper] Found {len(industry_articles)} industry articles")

        if source_pref in ["financial", "both"]:
            financial_articles = self._scrape_financial(topics, keywords, max_articles_per_source)
            all_articles.extend(financial_articles)
            stats["financial"] = len(financial_articles)
            print(f"[UserScraper] Found {len(financial_articles)} financial articles")

        # Process and save articles
        saved_count = self._process_and_save_articles(db, all_articles)

        return {
            "success": True,
            "message": f"Scraped {len(all_articles)} articles, saved {saved_count} new articles",
            "articles_scraped": len(all_articles),
            "articles_saved": saved_count,
            "by_source": stats,
            "topics": topics,
            "keywords": keywords
        }

    def scrape_for_user_with_tracking(
        self,
        db: Session,
        user_id: int,
        job_id: int,
        max_articles_per_source: int = 10
    ) -> Dict[str, any]:
        """
        Scrape articles with detailed progress tracking using ScrapingJob

        This version updates the job status in real-time with user-friendly messages
        """
        job = db.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()
        if not job:
            return {"success": False, "message": "Job not found"}

        try:
            # Update job: Starting
            job.status = "running"
            job.started_at = datetime.utcnow()
            job.current_step = "initializing"
            job.message = "Setting up your personalized content search..."
            db.commit()

            # Get user and preferences
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError(f"User {user_id} not found")

            prefs = user.preferences or {}
            topics = prefs.get("topics", [])
            keywords = prefs.get("keywords", [])
            source_pref = prefs.get("source", "both")

            if not topics:
                job.status = "failed"
                job.error_message = "No topics set in preferences"
                job.message = "Please set your topics in preferences first"
                db.commit()
                return {"success": False, "message": "No topics set"}

            all_articles = []
            stats = {"academic": 0, "industry": 0, "financial": 0}

            # Check for cancellation before starting
            db.refresh(job)
            if job.status == "cancelled":
                return {"success": False, "message": "Job cancelled by user"}

            # Scrape academic sources
            if source_pref in ["academic", "both"]:
                # Check for cancellation
                db.refresh(job)
                if job.status == "cancelled":
                    return {"success": False, "message": "Job cancelled by user"}

                job.current_step = "fetching_academic"
                job.message = f"Searching academic sources for {', '.join(topics[:2])}..."
                db.commit()

                academic_articles = self._scrape_academic(topics, keywords, max_articles_per_source)
                all_articles.extend(academic_articles)
                stats["academic"] = len(academic_articles)

            # Scrape industry sources
            if source_pref in ["industry", "both"]:
                # Check for cancellation
                db.refresh(job)
                if job.status == "cancelled":
                    return {"success": False, "message": "Job cancelled by user"}

                job.current_step = "fetching_industry"
                job.message = "Finding latest tech industry insights..."
                db.commit()

                industry_articles = self._scrape_industry(topics, keywords, max_articles_per_source)
                all_articles.extend(industry_articles)
                stats["industry"] = len(industry_articles)

            # Scrape financial sources
            if source_pref in ["financial", "both"]:
                # Check for cancellation
                db.refresh(job)
                if job.status == "cancelled":
                    return {"success": False, "message": "Job cancelled by user"}

                job.current_step = "fetching_financial"
                job.message = "Gathering financial news and analysis..."
                db.commit()

                financial_articles = self._scrape_financial(topics, keywords, max_articles_per_source)
                all_articles.extend(financial_articles)
                stats["financial"] = len(financial_articles)

            # Check for cancellation before processing
            db.refresh(job)
            if job.status == "cancelled":
                return {"success": False, "message": "Job cancelled by user"}

            # Update job with articles found
            job.total_articles_found = len(all_articles)
            job.source_stats = stats
            job.current_step = "processing"
            job.message = f"Processing {len(all_articles)} articles - analyzing content and removing duplicates..."
            db.commit()

            # Process and save articles with progress tracking
            saved_count = self._process_and_save_articles_with_tracking(db, all_articles, job)

            # Mark as completed with contextual messages
            job.status = "completed"
            job.current_step = "completed"
            job.articles_saved = saved_count
            job.completed_at = datetime.utcnow()

            # Provide contextual messages based on results
            if saved_count == 0:
                if len(all_articles) == 0:
                    job.message = "No news found matching your topics and keywords. Try adjusting your preferences or adding different topics."
                else:
                    job.message = f"Analyzed {len(all_articles)} articles — {len(all_articles) - saved_count} were already saved or too similar to existing content. Try scraping again later for fresher articles."
            elif saved_count < 3:
                job.message = f"Analysis completed! Found {saved_count} new article{'s' if saved_count > 1 else ''} for you."
            else:
                job.message = f"Done! Found {saved_count} new articles tailored to your interests."

            db.commit()

            return {
                "success": True,
                "message": f"Successfully saved {saved_count} new articles",
                "articles_scraped": len(all_articles),
                "articles_saved": saved_count,
                "by_source": stats,
                "topics": topics,
                "keywords": keywords
            }

        except Exception as e:
            job.status = "failed"
            job.current_step = "failed"
            job.error_message = str(e)
            job.message = "Something went wrong while finding articles. Please try again."
            job.completed_at = datetime.utcnow()
            db.commit()
            raise e

    def _process_and_save_articles_with_tracking(
        self,
        db: Session,
        articles: List[Dict],
        job: ScrapingJob
    ) -> int:
        """Process and save articles with progress updates to job"""
        saved_count = 0
        failed_count = 0
        total = len(articles)

        # Handle empty article list
        if total == 0:
            job.message = "No articles found matching your topics and keywords."
            db.commit()
            return 0

        for idx, article_data in enumerate(articles, 1):
            try:
                # Check for cancellation every 3 articles
                if idx % 3 == 0:
                    db.refresh(job)
                    if job.status == "cancelled":
                        print(f"[UserScraper] Job cancelled during processing at article {idx}/{total}")
                        return saved_count

                # Update progress every 3 articles for better feedback
                if idx % 3 == 0 or idx == total:
                    job.articles_processed = idx
                    job.message = f"Analyzing article {idx} of {total}... ({saved_count} saved, {failed_count} skipped)"
                    db.commit()

                # Check if article already exists
                existing = db.query(Article).filter(Article.url == article_data["url"]).first()
                if existing:
                    failed_count += 1
                    continue

                # Generate embedding with timeout protection
                try:
                    content_for_embedding = f"{article_data['title']} {article_data['content']}"
                    embedding = openai_service.generate_embedding(content_for_embedding, timeout=30)
                except Exception as embed_error:
                    print(f"[UserScraper] Embedding failed for article '{article_data.get('title', 'unknown')}': {embed_error}")
                    failed_count += 1
                    continue

                # Check for duplicates
                try:
                    if deduplication_service.is_duplicate(db, embedding, article_data["source_type"]):
                        failed_count += 1
                        continue
                except Exception as dedup_error:
                    print(f"[UserScraper] Deduplication check failed: {dedup_error}")
                    # Continue anyway, better to save than to skip

                # Generate AI summary with timeout protection
                try:
                    summary_data = openai_service.summarize_article(
                        content=article_data["content"],
                        source_type=article_data["source_type"],
                        title=article_data["title"],
                        timeout=60
                    )
                except Exception as summary_error:
                    print(f"[UserScraper] Summarization failed for article '{article_data.get('title', 'unknown')}': {summary_error}")
                    # Use fallback summary instead of skipping
                    summary_data = {
                        "summary": article_data.get("content", "")[:500] + "...",
                        "key_points": [],
                        "tags": []
                    }

                # Create article
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
                saved_count += 1

                # Commit in batches with error handling
                if saved_count % 3 == 0:
                    try:
                        db.commit()
                    except Exception as commit_error:
                        print(f"[UserScraper] Batch commit error: {commit_error}")
                        db.rollback()

            except Exception as e:
                print(f"[UserScraper] Error processing article: {e}")
                failed_count += 1
                continue

        # Final commit with error handling
        try:
            db.commit()
            print(f"[UserScraper] Processing complete: {saved_count} saved, {failed_count} failed/skipped out of {total} total")
        except Exception as final_commit_error:
            print(f"[UserScraper] Final commit error: {final_commit_error}")
            db.rollback()

        return saved_count

    def _scrape_academic(
        self,
        topics: List[str],
        keywords: List[str],
        max_results: int = 10
    ) -> List[Dict]:
        """Scrape academic sources (arXiv) based on topics and keywords"""
        articles = []
        categories_to_search = set()

        # Map user topics to arXiv categories using comprehensive mapping
        for topic in topics:
            topic_lower = topic.lower().strip()

            # Direct mapping check
            if topic_lower in ARXIV_CATEGORIES:
                categories_to_search.update(ARXIV_CATEGORIES[topic_lower][:3])
                print(f"[UserScraper] Mapped topic '{topic}' to categories: {ARXIV_CATEGORIES[topic_lower][:3]}")
            else:
                # Partial match check
                for domain, categories in ARXIV_CATEGORIES.items():
                    if domain in topic_lower or topic_lower in domain:
                        categories_to_search.update(categories[:3])
                        print(f"[UserScraper] Partial match: '{topic}' -> '{domain}' categories: {categories[:3]}")
                        break

        # If we found relevant categories, use RSS feeds (more reliable)
        if categories_to_search:
            print(f"[UserScraper] Searching {len(categories_to_search)} arXiv categories via RSS")
            try:
                rss_articles = self.arxiv_scraper.scrape_by_rss(list(categories_to_search))
                articles.extend(rss_articles)
                print(f"[UserScraper] Found {len(rss_articles)} articles from RSS feeds")
            except Exception as e:
                print(f"[UserScraper] RSS feed error: {e}, falling back to API")

                # Fallback to API if RSS fails
                try:
                    api_articles = self.arxiv_scraper.scrape_by_categories(list(categories_to_search)[:3])
                    articles.extend(api_articles)
                    print(f"[UserScraper] Found {len(api_articles)} articles from API")
                except Exception as api_error:
                    print(f"[UserScraper] API also failed: {api_error}")

        # Also try keyword-based search for topics without category mapping
        unmapped_topics = [t for t in topics if t.lower() not in ARXIV_CATEGORIES and
                          not any(t.lower() in domain or domain in t.lower() for domain in ARXIV_CATEGORIES.keys())]

        if unmapped_topics:
            print(f"[UserScraper] Searching unmapped topics via keyword search: {unmapped_topics}")
            for topic in unmapped_topics[:2]:  # Limit to avoid rate limits
                try:
                    topic_articles = self.arxiv_scraper.scrape_by_topics([topic])
                    articles.extend(topic_articles[:max_results])
                except Exception as e:
                    print(f"[UserScraper] Error scraping arXiv for topic '{topic}': {e}")
                    continue

        print(f"[UserScraper] Total academic articles found: {len(articles)}")
        return articles

    def _scrape_industry(
        self,
        topics: List[str],
        keywords: List[str],
        max_results: int = 10
    ) -> List[Dict]:
        """Scrape industry sources based on topics and keywords"""
        # Query active industry feeds from database
        db = SessionLocal()
        try:
            industry_feeds_db = RSSFeed.get_active_feeds_by_type(db, "industry")

            if not industry_feeds_db:
                print("[UserScraper] No active industry RSS feeds found in database")
                return []

            # Extract URLs
            feed_urls = [feed.url for feed in industry_feeds_db]
            print(f"[UserScraper] Scraping {len(feed_urls)} industry feeds from database")

            articles = self.rss_scraper.scrape_multiple_feeds(
                feed_urls,
                source_type="industry",
                limit=max_results
            )

            # Filter by topic relevance (basic keyword matching)
            filtered = self._filter_by_relevance(articles, topics, keywords)

            return filtered
        finally:
            db.close()

    def _scrape_financial(
        self,
        topics: List[str],
        keywords: List[str],
        max_results: int = 10
    ) -> List[Dict]:
        """Scrape financial sources based on topics and keywords"""
        # Query active financial feeds from database
        db = SessionLocal()
        try:
            financial_feeds_db = RSSFeed.get_active_feeds_by_type(db, "financial")

            if not financial_feeds_db:
                print("[UserScraper] No active financial RSS feeds found in database")
                return []

            # Extract URLs
            feed_urls = [feed.url for feed in financial_feeds_db]
            print(f"[UserScraper] Scraping {len(feed_urls)} financial feeds from database")

            articles = self.rss_scraper.scrape_multiple_feeds(
                feed_urls,
                source_type="financial",
                limit=max_results
            )

            # Filter by topic relevance
            filtered = self._filter_by_relevance(articles, topics, keywords)

            return filtered
        finally:
            db.close()

    def _get_expanded_terms(self, topics: List[str], keywords: List[str]) -> List[str]:
        """Expand topics to include synonyms and related terms for broader matching"""
        all_terms = [kw.lower() for kw in keywords]  # Start with explicit keywords
        for topic in topics:
            topic_lower = topic.lower().strip()
            all_terms.append(topic_lower)
            # Add synonyms if we have a direct match
            if topic_lower in TOPIC_SYNONYMS:
                all_terms.extend(TOPIC_SYNONYMS[topic_lower])
            else:
                # Partial match: e.g. "AI Development" matches the "ai" synonym list
                for key, synonyms in TOPIC_SYNONYMS.items():
                    if key in topic_lower or topic_lower in key:
                        all_terms.extend(synonyms)
        return list(set(all_terms))  # deduplicate

    def _filter_by_relevance(
        self,
        articles: List[Dict],
        topics: List[str],
        keywords: List[str]
    ) -> List[Dict]:
        """Filter articles by topic and keyword relevance with synonym expansion"""
        if not topics and not keywords:
            return articles

        # Expand topics to include synonyms so "AI" matches "machine learning", etc.
        expanded_terms = self._get_expanded_terms(topics, keywords)
        print(f"[UserScraper] Filtering with expanded terms: {expanded_terms[:10]}...")

        relevant_articles = []

        for article in articles:
            title_lower = article.get("title", "").lower()
            content_lower = article.get("content", "").lower()
            combined = title_lower + " " + content_lower

            if any(term in combined for term in expanded_terms):
                relevant_articles.append(article)

        print(f"[UserScraper] Relevance filter: {len(relevant_articles)}/{len(articles)} articles passed")

        # If no relevant articles found, return ALL (not just 5) to avoid blocking saves
        if not relevant_articles and articles:
            print(f"[UserScraper] No keyword matches — returning all {len(articles)} articles as fallback")
            return articles

        return relevant_articles

    def _process_and_save_articles(
        self,
        db: Session,
        articles: List[Dict]
    ) -> int:
        """
        Process articles (generate embeddings, summaries) and save to database

        Returns:
            Number of articles successfully saved
        """
        saved_count = 0

        for article_data in articles:
            try:
                # Check if article already exists (by URL)
                existing = db.query(Article).filter(Article.url == article_data["url"]).first()
                if existing:
                    continue

                # Generate embedding
                content_for_embedding = f"{article_data['title']} {article_data['content']}"
                embedding = openai_service.generate_embedding(content_for_embedding)

                # Check for duplicates using embedding similarity
                if deduplication_service.is_duplicate(db, embedding, article_data["source_type"]):
                    print(f"[UserScraper] Skipping duplicate: {article_data['title'][:50]}...")
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
                saved_count += 1

                # Commit in batches
                if saved_count % 5 == 0:
                    db.commit()
                    print(f"[UserScraper] Processed {saved_count} articles...")

            except Exception as e:
                print(f"[UserScraper] Error processing article: {e}")
                continue

        # Final commit
        db.commit()
        print(f"[UserScraper] Successfully saved {saved_count} unique articles")

        return saved_count

    def scrape_for_all_active_users(
        self,
        db: Session,
        max_articles_per_source: int = 5
    ) -> Dict[str, any]:
        """
        Scrape articles for all active users with preferences set

        Useful for batch processing or scheduled tasks
        """
        users = db.query(User).filter(User.is_active == True).all()

        results = []
        total_scraped = 0
        total_saved = 0

        for user in users:
            # Skip users without topics
            if not user.preferences or not user.preferences.get("topics"):
                continue

            try:
                result = self.scrape_for_user(db, user.id, max_articles_per_source)
                results.append({
                    "user_id": user.id,
                    "email": user.email,
                    **result
                })
                total_scraped += result["articles_scraped"]
                total_saved += result["articles_saved"]
            except Exception as e:
                print(f"Error scraping for user {user.id}: {e}")
                continue

        return {
            "success": True,
            "users_processed": len(results),
            "total_articles_scraped": total_scraped,
            "total_articles_saved": total_saved,
            "user_results": results
        }


# Singleton instance
user_scraper_service = UserScraperService()
