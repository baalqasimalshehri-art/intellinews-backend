import json
from typing import List, Dict, Optional
from openai import OpenAI
from app.config import settings
from app.prompts.summarization import get_prompt_by_source_type, RANKING_REASONING_PROMPT


class OpenAIService:
    """Service for interacting with OpenAI API (GPT-4 and embeddings)"""

    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.embedding_model = settings.EMBEDDING_MODEL
        self.embedding_dimension = settings.EMBEDDING_DIMENSION
        self.gpt_model = settings.GPT_MODEL

    def generate_embedding(self, text: str, timeout: int = 30) -> List[float]:
        """
        Generate vector embedding for text using OpenAI embeddings

        Args:
            text: Input text to embed
            timeout: Maximum time in seconds to wait for response (default: 30)

        Returns:
            List of floats representing the embedding vector
        """
        try:
            # Truncate text to fit within embedding model's token limit
            # text-embedding-3-large has 8192 token limit
            # Use conservative estimate: 1 token ≈ 3 characters (safer than 4)
            # Target 6000 tokens to leave safety margin for overhead
            max_chars = 6000 * 3  # ~18000 characters = ~6000 tokens (safe limit)

            if len(text) > max_chars:
                print(f"[OpenAI] Truncating text from {len(text)} to {max_chars} characters for embedding")
                text = text[:max_chars]

            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=text,
                dimensions=self.embedding_dimension,  # Use configured embedding dimension
                timeout=timeout  # Add timeout protection
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"[OpenAI] Error generating embedding (timeout={timeout}s): {e}")
            raise

    def summarize_article(
        self,
        content: str,
        source_type: str,
        title: Optional[str] = None,
        timeout: int = 60
    ) -> Dict:
        """
        Summarize article using GPT-4 with context-aware prompts

        Args:
            content: Full article content
            source_type: Type of content ("academic", "industry", "financial")
            title: Optional article title for context
            timeout: Maximum time in seconds to wait for response (default: 60)

        Returns:
            Dictionary with summary, key_points, and tags
        """
        # Get appropriate prompt based on source type
        prompt_template = get_prompt_by_source_type(source_type)

        # Truncate content if too long (GPT-4 context limit)
        max_content_length = 12000  # ~3000 tokens
        if len(content) > max_content_length:
            content = content[:max_content_length] + "..."

        prompt = prompt_template.format(content=content)

        try:
            response = self.client.chat.completions.create(
                model=self.gpt_model,
                messages=[
                    {"role": "system", "content": "You are an AI assistant that summarizes content accurately and concisely."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=settings.MAX_TOKENS,
                temperature=0.3,  # Lower temperature for more consistent summaries
                response_format={"type": "json_object"},
                timeout=timeout  # Add timeout protection
            )

            result = json.loads(response.choices[0].message.content)

            return {
                "summary": result.get("summary", ""),
                "key_points": result.get("keyPoints", []),
                "tags": result.get("tags", [])
            }
        except Exception as e:
            print(f"[OpenAI] Error summarizing article (timeout={timeout}s): {e}")
            # Return a fallback summary
            return {
                "summary": f"Error generating summary: {str(e)}",
                "key_points": [],
                "tags": []
            }

    def generate_ranking_reasoning(
        self,
        article_title: str,
        article_source: str,
        source_type: str,
        published_date: str,
        user_topics: List[str],
        user_keywords: List[str],
        relevance_score: float,
        freshness_score: float,
        final_score: float
    ) -> str:
        """
        Generate AI explanation for why an article was ranked for a user

        Args:
            article_title: Title of the article
            article_source: Source of the article
            source_type: Type of content
            published_date: When article was published
            user_topics: User's preferred topics
            user_keywords: User's preferred keywords
            relevance_score: Semantic relevance score
            freshness_score: Recency score
            final_score: Combined ranking score

        Returns:
            String explanation of the ranking
        """
        prompt = RANKING_REASONING_PROMPT.format(
            title=article_title,
            source=article_source,
            source_type=source_type,
            published_date=published_date,
            topics=", ".join(user_topics),
            keywords=", ".join(user_keywords),
            relevance_score=f"{relevance_score:.2f}",
            freshness_score=f"{freshness_score:.2f}",
            final_score=f"{final_score:.2f}"
        )

        try:
            response = self.client.chat.completions.create(
                model=self.gpt_model,
                messages=[
                    {"role": "system", "content": "You are an AI assistant explaining content recommendations."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.5,
                timeout=30  # Add timeout protection
            )

            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"[OpenAI] Error generating reasoning: {e}")
            topic_hint = user_topics[0] if user_topics else (user_keywords[0] if user_keywords else "your interests")
            return f"Matched your interest in {topic_hint} ({int(relevance_score * 100)}% relevance). Published {published_date}."

    def generate_user_preference_embedding(
        self,
        topics: List[str],
        keywords: List[str]
    ) -> List[float]:
        """
        Generate embedding for user preferences

        Args:
            topics: List of user's preferred topics
            keywords: List of user's preferred keywords

        Returns:
            Embedding vector representing user preferences
        """
        # Combine topics and keywords into a preference text
        preference_text = f"Topics: {', '.join(topics)}. Keywords: {', '.join(keywords)}."
        return self.generate_embedding(preference_text)


# Global instance
openai_service = OpenAIService()
