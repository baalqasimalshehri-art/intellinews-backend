import arxiv
import feedparser
from datetime import datetime
from typing import List, Dict
from app.config import settings
import time


class ArxivScraper:
    """Scraper for academic papers from arXiv"""

    def __init__(self):
        self.max_results = settings.ARXIV_MAX_RESULTS
        self.min_date = settings.min_article_datetime

    def scrape_by_topics(self, topics: List[str]) -> List[Dict]:
        """
        Scrape recent arXiv papers based on topics

        Args:
            topics: List of topics/categories to search (e.g., ["machine learning", "NLP"])

        Returns:
            List of article dictionaries
        """
        articles = []

        for topic in topics:
            # Build arXiv query
            search = arxiv.Search(
                query=topic,
                max_results=self.max_results,
                sort_by=arxiv.SortCriterion.SubmittedDate,
                sort_order=arxiv.SortOrder.Descending
            )

            for result in search.results():
                # Filter by date (only 2025+)
                published = result.published.replace(tzinfo=None)
                if published < self.min_date:
                    continue

                article = {
                    "title": result.title,
                    "content": result.summary,
                    "url": result.entry_id,
                    "source": "arXiv",
                    "source_type": "academic",
                    "published_date": published,
                    "metadata": {
                        "authors": [author.name for author in result.authors],
                        "categories": result.categories,
                        "primary_category": result.primary_category,
                        "pdf_url": result.pdf_url
                    }
                }

                articles.append(article)

        return articles

    def scrape_by_categories(self, categories: List[str]) -> List[Dict]:
        """
        Scrape papers from specific arXiv categories using API

        Args:
            categories: arXiv category codes (e.g., ["cs.AI", "cs.CL", "cs.LG"])

        Returns:
            List of article dictionaries
        """
        articles = []

        for category in categories:
            try:
                # Build query for specific category
                query = f"cat:{category}"
                search = arxiv.Search(
                    query=query,
                    max_results=self.max_results,
                    sort_by=arxiv.SortCriterion.SubmittedDate,
                    sort_order=arxiv.SortOrder.Descending
                )

                for result in search.results():
                    published = result.published.replace(tzinfo=None)
                    if published < self.min_date:
                        continue

                    article = {
                        "title": result.title,
                        "content": result.summary,
                        "url": result.entry_id,
                        "source": "arXiv",
                        "source_type": "academic",
                        "published_date": published,
                        "metadata": {
                            "authors": [author.name for author in result.authors],
                            "categories": result.categories,
                            "primary_category": result.primary_category,
                            "pdf_url": result.pdf_url
                        }
                    }

                    articles.append(article)

                # Rate limiting - be respectful to arXiv
                time.sleep(3)

            except Exception as e:
                print(f"Error scraping arXiv category {category}: {e}")
                continue

        return articles

    def scrape_by_rss(self, categories: List[str]) -> List[Dict]:
        """
        Scrape papers from arXiv using RSS feeds (alternative to API)
        More reliable for recent papers, updated daily at midnight EST

        Args:
            categories: arXiv category codes (e.g., ["cs.AI", "cs.CL"])

        Returns:
            List of article dictionaries
        """
        articles = []

        for category in categories:
            try:
                # Construct RSS feed URL
                rss_url = f"https://rss.arxiv.org/rss/{category}"
                print(f"[ArxivScraper] Fetching RSS feed from {rss_url}")

                # Parse RSS feed
                feed = feedparser.parse(rss_url)

                if not feed.entries:
                    print(f"[ArxivScraper] No entries found in RSS feed for {category}")
                    continue

                for entry in feed.entries[:self.max_results]:
                    # Parse publication date
                    pub_date = datetime.strptime(entry.published, "%a, %d %b %Y %H:%M:%S %z")
                    published = pub_date.replace(tzinfo=None)

                    if published < self.min_date:
                        continue

                    # Extract summary (remove arXiv: prefix if present)
                    summary = entry.summary
                    if summary.startswith("arXiv:"):
                        summary = summary.split("\n", 1)[1] if "\n" in summary else summary

                    # Extract arXiv ID from link
                    arxiv_id = entry.id.split("/abs/")[-1] if "/abs/" in entry.id else entry.id

                    article = {
                        "title": entry.title,
                        "content": summary.strip(),
                        "url": entry.link,
                        "source": "arXiv",
                        "source_type": "academic",
                        "published_date": published,
                        "metadata": {
                            "authors": [entry.author] if hasattr(entry, "author") else [],
                            "categories": [category],
                            "primary_category": category,
                            "arxiv_id": arxiv_id,
                            "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}"
                        }
                    }

                    articles.append(article)

                print(f"[ArxivScraper] Found {len(articles)} articles from RSS feed {category}")

            except Exception as e:
                print(f"Error scraping arXiv RSS for category {category}: {e}")
                continue

        return articles


# Common arXiv categories for different domains
# Comprehensive mapping of topics to arXiv categories
ARXIV_CATEGORIES = {
    # AI and Machine Learning
    "ai": ["cs.AI", "cs.LG", "cs.CL", "cs.CV", "cs.NE"],
    "artificial intelligence": ["cs.AI", "cs.LG", "cs.CL", "cs.CV"],
    "machine learning": ["cs.LG", "stat.ML", "cs.AI"],
    "deep learning": ["cs.LG", "cs.CV", "cs.CL", "cs.NE"],
    "neural networks": ["cs.NE", "cs.LG", "cs.AI"],
    "nlp": ["cs.CL", "cs.AI", "cs.LG"],
    "natural language processing": ["cs.CL", "cs.AI", "cs.LG"],
    "computer vision": ["cs.CV", "cs.LG", "cs.AI"],
    "llm": ["cs.CL", "cs.AI", "cs.LG"],
    "llms": ["cs.CL", "cs.AI", "cs.LG"],
    "large language models": ["cs.CL", "cs.AI", "cs.LG"],
    "transformers": ["cs.CL", "cs.LG", "cs.AI"],
    "gpt": ["cs.CL", "cs.AI", "cs.LG"],

    # Biology and Biotech
    "biology": ["q-bio.BM", "q-bio.NC", "q-bio.QM", "q-bio.GN"],
    "biotech": ["q-bio.BM", "q-bio.QM", "q-bio.MN", "physics.bio-ph"],
    "biotechnology": ["q-bio.BM", "q-bio.QM", "q-bio.MN", "physics.bio-ph"],
    "bioinformatics": ["q-bio.QM", "q-bio.GN", "cs.CE"],
    "genomics": ["q-bio.GN", "q-bio.QM"],
    "neuroscience": ["q-bio.NC", "q-bio.BM"],
    "computational biology": ["q-bio.QM", "q-bio.MN", "cs.CE"],

    # Physics
    "physics": ["physics.comp-ph", "quant-ph", "cond-mat"],
    "quantum": ["quant-ph", "cond-mat.mes-hall", "physics.atom-ph"],
    "quantum computing": ["quant-ph", "cs.ET", "cs.CC"],

    # Math and Statistics
    "math": ["math.OC", "math.ST", "stat.ML"],
    "mathematics": ["math.OC", "math.ST", "math.NA"],
    "statistics": ["stat.ML", "math.ST", "stat.ME"],

    # Computer Science
    "robotics": ["cs.RO", "cs.AI", "cs.LG"],
    "computer science": ["cs.AI", "cs.LG", "cs.CL"],
    "software engineering": ["cs.SE", "cs.PL"],
    "cryptography": ["cs.CR", "cs.IT"],
    "databases": ["cs.DB", "cs.IR"],

    # Economics and Finance
    "economics": ["econ.EM", "econ.TH", "q-fin.CP"],
    "finance": ["q-fin.CP", "q-fin.PM", "q-fin.RM"],
    "econometrics": ["econ.EM", "stat.ME"]
}
