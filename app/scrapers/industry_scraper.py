import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict
from app.config import settings


class IndustryScraper:
    """Scraper for industry news from various tech sources"""

    def __init__(self):
        self.min_date = settings.min_article_datetime

    def scrape_techcrunch(self, categories: List[str] = None) -> List[Dict]:
        """
        Scrape TechCrunch articles using RSS feeds

        Args:
            categories: List of categories to scrape (defaults to all)

        Returns:
            List of article dictionaries
        """
        articles = []
        base_url = "https://techcrunch.com/feed/"

        try:
            feed = feedparser.parse(base_url)

            for entry in feed.entries:
                # Parse published date
                published = datetime(*entry.published_parsed[:6])

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
                    "source": "TechCrunch",
                    "source_type": "industry",
                    "published_date": published,
                    "metadata": {
                        "author": entry.get("author", ""),
                        "tags": [tag.term for tag in entry.get("tags", [])]
                    }
                }

                articles.append(article)

        except Exception as e:
            print(f"Error scraping TechCrunch: {e}")

        return articles

    def scrape_hackernews(self, limit: int = 50) -> List[Dict]:
        """
        Scrape top stories from Hacker News

        Args:
            limit: Maximum number of stories to fetch

        Returns:
            List of article dictionaries
        """
        articles = []
        base_url = "https://hacker-news.firebaseio.com/v0"

        try:
            # Get top story IDs
            response = requests.get(f"{base_url}/topstories.json", timeout=10)
            story_ids = response.json()[:limit]

            for story_id in story_ids:
                # Get story details
                story_response = requests.get(f"{base_url}/item/{story_id}.json", timeout=10)
                story = story_response.json()

                # Skip if no URL or is a discussion (Ask HN, etc.)
                if not story.get("url") or story.get("type") != "story":
                    continue

                # Parse timestamp
                published = datetime.fromtimestamp(story.get("time", 0))

                # Filter by date
                if published < self.min_date:
                    continue

                # Fetch article content if available
                content = story.get("text", "")
                if not content and story.get("url"):
                    # Could optionally scrape the linked page here
                    content = f"Story from Hacker News: {story.get('title')}"

                article = {
                    "title": story.get("title", ""),
                    "content": content,
                    "url": story.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                    "source": "Hacker News",
                    "source_type": "industry",
                    "published_date": published,
                    "metadata": {
                        "score": story.get("score", 0),
                        "hn_id": story_id,
                        "descendants": story.get("descendants", 0)  # comment count
                    }
                }

                articles.append(article)

        except Exception as e:
            print(f"Error scraping Hacker News: {e}")

        return articles

    def scrape_rss_feed(self, feed_url: str, source_name: str) -> List[Dict]:
        """
        Generic RSS feed scraper

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
                    "source_type": "industry",
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


# Common industry RSS feeds
INDUSTRY_RSS_FEEDS = {
    "TechCrunch": "https://techcrunch.com/feed/",
    "VentureBeat": "https://venturebeat.com/feed/",
    "TheVerge": "https://www.theverge.com/rss/index.xml",
    "Wired": "https://www.wired.com/feed/rss",
    "MIT Technology Review": "https://www.technologyreview.com/feed/"
}
