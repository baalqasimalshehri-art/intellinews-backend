import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict
from app.config import settings


class FinancialScraper:
    """Scraper for financial news from various sources"""

    def __init__(self):
        self.min_date = settings.min_article_datetime

    def scrape_rss_feed(self, feed_url: str, source_name: str) -> List[Dict]:
        """
        Generic RSS feed scraper for financial news

        Args:
            feed_url: URL of the RSS feed
            source_name: Name of the source

        Returns:
            List of article dictionaries
        """
        articles = []

        try:
            feed = feedparser.parse(feed_url)

            for entry in feed.entries:
                # Parse published date
                if hasattr(entry, "published_parsed"):
                    published = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, "updated_parsed"):
                    published = datetime(*entry.updated_parsed[:6])
                else:
                    published = datetime.now()

                # Filter by date
                if published < self.min_date:
                    continue

                # Extract content
                content = entry.get("summary", "")
                if hasattr(entry, "content"):
                    content = entry.content[0].value

                # Clean HTML
                soup = BeautifulSoup(content, "html.parser")
                clean_content = soup.get_text()

                article = {
                    "title": entry.title,
                    "content": clean_content,
                    "url": entry.link,
                    "source": source_name,
                    "source_type": "financial",
                    "published_date": published,
                    "metadata": {
                        "author": entry.get("author", ""),
                        "tags": [tag.term for tag in entry.get("tags", [])]
                    }
                }

                articles.append(article)

        except Exception as e:
            print(f"Error scraping RSS feed {feed_url}: {e}")

        return articles

    def scrape_reuters_finance(self) -> List[Dict]:
        """Scrape Reuters finance news"""
        return self.scrape_rss_feed(
            "https://www.reutersagency.com/feed/?taxonomy=best-topics&post_type=best",
            "Reuters"
        )

    def scrape_ft(self) -> List[Dict]:
        """Scrape Financial Times (requires subscription or use RSS)"""
        return self.scrape_rss_feed(
            "https://www.ft.com/?format=rss",
            "Financial Times"
        )

    def scrape_wsj_markets(self) -> List[Dict]:
        """Scrape Wall Street Journal markets"""
        return self.scrape_rss_feed(
            "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
            "Wall Street Journal"
        )

    def scrape_bloomberg(self) -> List[Dict]:
        """
        Scrape Bloomberg news
        Note: Bloomberg has strict scraping policies, use RSS or API if available
        """
        return self.scrape_rss_feed(
            "https://www.bloomberg.com/feeds/podcasts/bloomberg_surveillance.xml",
            "Bloomberg"
        )


# Common financial RSS feeds
FINANCIAL_RSS_FEEDS = {
    "Reuters": "https://www.reutersagency.com/feed/?taxonomy=best-topics&post_type=best",
    "WSJ Markets": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "Financial Times": "https://www.ft.com/?format=rss",
    "MarketWatch": "https://www.marketwatch.com/rss/",
    "Seeking Alpha": "https://seekingalpha.com/feed.xml"
}
