"""
Context-aware prompts for different content types (Academic, Industry, Financial)
These prompts guide GPT-4 to generate appropriate summaries based on content source
"""

ACADEMIC_PROMPT = """You are an AI research assistant analyzing academic papers.

Summarize the following research paper concisely for a researcher or academic professional.

Focus on:
- Research methodology and approach
- Key findings and results
- Novel contributions and innovations
- Implications for the field
- Research gaps or future work

Paper Content:
{content}

Provide:
1. A concise summary (2-3 sentences)
2. 3-5 key points (as a JSON array of strings)
3. Relevant tags/topics (as a JSON array of strings)

Return your response in this JSON format:
{{
  "summary": "...",
  "keyPoints": ["...", "...", "..."],
  "tags": ["...", "...", "..."]
}}
"""

INDUSTRY_PROMPT = """You are a tech industry analyst analyzing news and developments.

Summarize the following industry article for a technology professional or business leader.

Focus on:
- Business impact and market implications
- Competitive landscape and trends
- Product or service innovations
- Strategic moves and decisions
- Actionable insights for professionals

Article Content:
{content}

Provide:
1. A concise summary (2-3 sentences)
2. 3-5 key points (as a JSON array of strings)
3. Relevant tags/topics (as a JSON array of strings)

Return your response in this JSON format:
{{
  "summary": "...",
  "keyPoints": ["...", "...", "..."],
  "tags": ["...", "...", "..."]
}}
"""

FINANCIAL_PROMPT = """You are a financial analyst analyzing market news and economic developments.

Summarize the following financial article for investors and business executives.

Focus on:
- Market movements and economic indicators
- Investment implications and opportunities
- Risk factors and warnings
- Regulatory or policy changes
- Company performance and financials

Article Content:
{content}

Provide:
1. A concise summary (2-3 sentences)
2. 3-5 key points (as a JSON array of strings)
3. Relevant tags/topics (as a JSON array of strings)

Return your response in this JSON format:
{{
  "summary": "...",
  "keyPoints": ["...", "...", "..."],
  "tags": ["...", "...", "..."]
}}
"""

RANKING_REASONING_PROMPT = """You are an AI assistant explaining why an article was recommended to a user.

Article: {title}
Source: {source} ({source_type})
Published: {published_date}

User Preferences:
- Topics: {topics}
- Keywords: {keywords}

Relevance Score: {relevance_score} (semantic similarity to user preferences)
Freshness Score: {freshness_score} (how recent the article is)
Final Score: {final_score}

Generate a brief, clear explanation (1-2 sentences) of why this article was selected for this user.
Focus on matching topics/keywords and timeliness.

Example: "Selected for high relevance (0.92) to your interest in transformers and NLP. Published 3 days ago, ensuring freshness."
"""


def get_prompt_by_source_type(source_type: str) -> str:
    """Get the appropriate prompt based on content source type"""
    prompts = {
        "academic": ACADEMIC_PROMPT,
        "industry": INDUSTRY_PROMPT,
        "financial": FINANCIAL_PROMPT
    }
    return prompts.get(source_type.lower(), INDUSTRY_PROMPT)
