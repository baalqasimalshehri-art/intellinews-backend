"""
RSS Feed Scraper - Replacement for Firecrawl

This scraper uses RSS/Atom feeds to collect articles from various sources.
It's faster, more reliable, and doesn't require API keys.
"""

from typing import List, Dict
from datetime import datetime
import feedparser
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from app.config import settings


class RSSFeedScraper:
    """RSS feed scraper for collecting articles from various sources"""

    def __init__(self):
        self.min_date = settings.min_article_datetime
        # Create session with timeout and retry logic
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def scrape_feed(self, feed_url: str, source_type: str = "industry", limit: int = 10) -> List[Dict]:
        """
        Scrape articles from an RSS feed

        Args:
            feed_url: URL of the RSS feed
            source_type: Type of content ("academic", "industry", "financial")
            limit: Maximum number of articles to return

        Returns:
            List of article dictionaries
        """
        try:
            # Fetch with timeout
            response = self.session.get(feed_url, timeout=15)
            feed = feedparser.parse(response.content)
            articles = []

            for entry in feed.entries[:limit]:
                try:
                    # Parse published date
                    published_date = self._parse_date(entry)

                    # Skip old articles
                    if published_date and published_date < self.min_date:
                        continue

                    # Extract content
                    content = self._extract_content(entry)

                    # Get source from feed or entry link
                    source = feed.feed.get('title', '')
                    if not source and hasattr(entry, 'link'):
                        source = entry.link.split('/')[2] if '/' in entry.link else ''

                    article = {
                        "title": entry.get('title', ''),
                        "content": content,
                        "url": entry.get('link', ''),
                        "source": source,
                        "source_type": source_type,
                        "published_date": published_date or datetime.utcnow(),
                        "metadata": {
                            "author": entry.get('author', ''),
                            "description": entry.get('summary', ''),
                            "tags": [tag.term for tag in entry.get('tags', [])]
                        }
                    }

                    if article["title"] and article["url"]:
                        articles.append(article)

                except Exception as e:
                    print(f"Error parsing feed entry: {e}")
                    continue

            return articles

        except requests.Timeout:
            print(f"[RSS] Timeout fetching {feed_url} (15s limit)")
            return []
        except requests.RequestException as e:
            print(f"[RSS] Request error for {feed_url}: {e}")
            return []
        except Exception as e:
            print(f"[RSS] Error scraping feed {feed_url}: {e}")
            return []

    def scrape_multiple_feeds(self, feed_urls: List[str], source_type: str = "industry", limit: int = 10) -> List[Dict]:
        """
        Scrape articles from multiple RSS feeds

        Args:
            feed_urls: List of RSS feed URLs
            source_type: Type of content
            limit: Maximum articles per feed

        Returns:
            Combined list of articles from all feeds
        """
        all_articles = []

        for feed_url in feed_urls:
            articles = self.scrape_feed(feed_url, source_type, limit)
            all_articles.extend(articles)
            print(f"Scraped {len(articles)} articles from {feed_url}")

        return all_articles

    def _extract_content(self, entry) -> str:
        """Extract content from feed entry"""
        # Try different content fields in order of preference
        if hasattr(entry, 'content') and entry.content:
            return entry.content[0].value
        elif hasattr(entry, 'summary'):
            return entry.summary
        elif hasattr(entry, 'description'):
            return entry.description
        else:
            return ""

    def _parse_date(self, entry) -> datetime:
        """Parse published date from feed entry"""
        try:
            # Try different date fields
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                return datetime(*entry.published_parsed[:6])
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                return datetime(*entry.updated_parsed[:6])
            else:
                return datetime.utcnow()
        except Exception:
            return datetime.utcnow()


# Common RSS feed sources
RSS_FEEDS = {
    "techcrunch": "https://techcrunch.com/feed/",
    "venturebeat": "https://venturebeat.com/feed/",
    "wired": "https://www.wired.com/feed/rss",
    "theverge": "https://www.theverge.com/rss/index.xml",
    "arstechnica": "https://feeds.arstechnica.com/arstechnica/index",
    "hackernews": "https://hnrss.org/frontpage",
    "reuters_tech": "https://www.reuters.com/technology",
    "bbc_tech": "http://feeds.bbci.co.uk/news/technology/rss.xml",
    "mit_tech_review": "https://www.technologyreview.com/feed/",
}
