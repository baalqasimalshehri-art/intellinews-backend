import resend
from typing import List
from datetime import datetime
from app.config import settings


class EmailService:
    """Service for sending emails using Resend API"""

    def __init__(self):
        self.resend_api_key = settings.RESEND_API_KEY
        self.from_email = settings.FROM_EMAIL
        self.frontend_url = settings.FRONTEND_URL
        if self.resend_api_key:
            resend.api_key = self.resend_api_key

    def send_newsletter(
        self,
        to_email: str,
        user_name: str,
        articles: List[dict],
        frequency: str = "daily"
    ) -> bool:
        """
        Send personalized newsletter with ranked articles

        Args:
            to_email: Recipient email address
            user_name: Recipient name
            articles: List of article dictionaries with ranking info
            frequency: Newsletter frequency (daily, weekly, monthly)

        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.resend_api_key:
            print(f"[Email] Skipping newsletter to {to_email}: RESEND_API_KEY not configured")
            return False

        try:
            # Generate HTML content
            html_content = self._generate_newsletter_html(
                user_name=user_name,
                articles=articles,
                frequency=frequency
            )

            # Send email using Resend API
            params = {
                "from": self.from_email,
                "to": [to_email],
                "subject": f"Your {frequency.capitalize()} IntelliNews Brief - {datetime.now().strftime('%B %d, %Y')}",
                "html": html_content,
            }

            email = resend.Emails.send(params)
            print(f"Newsletter sent successfully to {to_email} (Resend ID: {email.get('id', 'N/A')})")
            return True

        except Exception as e:
            print(f"Error sending newsletter to {to_email}: {e}")
            print(f"Error type: {type(e).__name__}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")
            return False

    def _generate_newsletter_html(
        self,
        user_name: str,
        articles: List[dict],
        frequency: str
    ) -> str:
        """
        Generate HTML content for newsletter

        Args:
            user_name: Recipient name
            articles: List of article dictionaries
            frequency: Newsletter frequency

        Returns:
            HTML string
        """
        # Start HTML
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IntelliNews Brief</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #1e293b;
            background-color: #f8fafc;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background-color: #ffffff;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }}
        .header {{
            background: linear-gradient(135deg, #9810fa 0%, #6366f1 100%);
            color: white;
            padding: 40px 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
            font-weight: 800;
        }}
        .header p {{
            margin: 10px 0 0 0;
            opacity: 0.9;
            font-size: 14px;
        }}
        .content {{
            padding: 30px;
        }}
        .greeting {{
            font-size: 18px;
            margin-bottom: 20px;
            color: #334155;
        }}
        .article {{
            margin-bottom: 30px;
            padding-bottom: 30px;
            border-bottom: 1px solid #e2e8f0;
        }}
        .article:last-child {{
            border-bottom: none;
        }}
        .article-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }}
        .source-badge {{
            background-color: #f1f5f9;
            color: #64748b;
            padding: 4px 12px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .score-badge {{
            background-color: #10b981;
            color: white;
            padding: 4px 12px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 700;
        }}
        .article-title {{
            font-size: 20px;
            font-weight: 700;
            color: #0f172a;
            margin: 10px 0;
            line-height: 1.4;
        }}
        .article-title a {{
            color: #0f172a;
            text-decoration: none;
        }}
        .article-title a:hover {{
            color: #9810fa;
        }}
        .article-summary {{
            color: #475569;
            font-size: 15px;
            margin: 15px 0;
            line-height: 1.6;
        }}
        .key-points {{
            background-color: #f8fafc;
            border-left: 3px solid #9810fa;
            padding: 15px 20px;
            margin: 15px 0;
        }}
        .key-points h4 {{
            margin: 0 0 10px 0;
            font-size: 13px;
            font-weight: 700;
            color: #475569;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .key-points ul {{
            margin: 0;
            padding-left: 20px;
        }}
        .key-points li {{
            color: #334155;
            font-size: 14px;
            margin-bottom: 8px;
        }}
        .reasoning {{
            background-color: #fef3c7;
            border-left: 3px solid #f59e0b;
            padding: 12px 16px;
            margin: 15px 0;
            font-size: 13px;
            color: #78350f;
            font-style: italic;
        }}
        .tags {{
            margin-top: 15px;
        }}
        .tag {{
            display: inline-block;
            background-color: #e0e7ff;
            color: #4338ca;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            margin-right: 8px;
            margin-bottom: 8px;
        }}
        .read-more {{
            display: inline-block;
            margin-top: 15px;
            padding: 10px 20px;
            background-color: #9810fa;
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            font-size: 14px;
        }}
        .read-more:hover {{
            background-color: #7c0fd1;
        }}
        .footer {{
            background-color: #f8fafc;
            padding: 30px;
            text-align: center;
            color: #64748b;
            font-size: 13px;
        }}
        .footer a {{
            color: #9810fa;
            text-decoration: none;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📰 IntelliNews</h1>
            <p>AI-Curated Intelligence Brief • {datetime.now().strftime('%B %d, %Y')}</p>
        </div>

        <div class="content">
            <div class="greeting">
                Hello {user_name},<br>
                Here are your top {len(articles)} articles curated by AI, ranked by relevance and freshness.
            </div>
"""

        # Add articles
        for idx, article in enumerate(articles, 1):
            html += f"""
            <div class="article">
                <div class="article-header">
                    <span class="source-badge">{article.get('source', 'Unknown')} • {article.get('sourceType', '').title()}</span>
                    <span class="score-badge">{int(article.get('finalScore', 0) * 100)}% Match</span>
                </div>

                <h2 class="article-title">
                    <a href="{article.get('url', '#')}" target="_blank">{article.get('title', 'Untitled')}</a>
                </h2>

                <div class="article-summary">
                    {article.get('summary', 'No summary available')}
                </div>
"""

            # Add key points if available
            if article.get('keyPoints'):
                html += """
                <div class="key-points">
                    <h4>📌 Key Points</h4>
                    <ul>
"""
                for point in article['keyPoints']:
                    html += f"                        <li>{point}</li>\n"
                html += """
                    </ul>
                </div>
"""

            # Add AI reasoning
            if article.get('reasoning'):
                html += f"""
                <div class="reasoning">
                    🤖 AI Insight: {article['reasoning']}
                </div>
"""

            # Add tags if available
            if article.get('tags'):
                html += """
                <div class="tags">
"""
                for tag in article['tags'][:5]:  # Limit to 5 tags
                    html += f'                    <span class="tag">#{tag}</span>\n'
                html += """
                </div>
"""

            html += f"""
                <a href="{article.get('url', '#')}" class="read-more" target="_blank">Read Full Article →</a>
            </div>
"""

        # Footer
        html += f"""
        </div>

        <div class="footer">
            <p>
                You're receiving this because you subscribed to {frequency} IntelliNews updates.<br>
                Powered by AI • RAG Retrieval • Intelligent Ranking
            </p>
            <p>
                <a href="#">Update Preferences</a> • <a href="#">Unsubscribe</a>
            </p>
        </div>
    </div>
</body>
</html>
"""

        return html

    def send_password_reset_email(
        self,
        to_email: str,
        reset_token: str,
        user_name: str = None
    ) -> bool:
        """
        Send password reset email with reset link

        Args:
            to_email: Recipient email address
            reset_token: Password reset token
            user_name: Optional user name for personalization

        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.resend_api_key:
            print(f"[Email] Skipping password reset to {to_email}: RESEND_API_KEY not configured")
            return False

        try:
            # Create reset link using configured frontend URL
            reset_link = f"{self.frontend_url}/#/reset-password?token={reset_token}"

            # Email subject
            subject = "IntelliNews - Password Reset Request"

            # Generate HTML content
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: linear-gradient(135deg, #9810FA 0%, #5B10DA 100%);
            color: white;
            padding: 30px;
            text-align: center;
            border-radius: 10px 10px 0 0;
        }}
        .content {{
            background: #f8f9fa;
            padding: 40px 30px;
            border-radius: 0 0 10px 10px;
        }}
        .button {{
            display: inline-block;
            padding: 14px 32px;
            background: #9810FA;
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-weight: bold;
            margin: 20px 0;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            color: #666;
            font-size: 12px;
        }}
        .warning {{
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔐 Password Reset Request</h1>
        </div>
        <div class="content">
            <p>Hello{f" {user_name}" if user_name else ""},</p>

            <p>We received a request to reset your IntelliNews password. Click the button below to create a new password:</p>

            <div style="text-align: center;">
                <a href="{reset_link}" class="button">Reset Your Password</a>
            </div>

            <div class="warning">
                <strong>⏰ This link expires in 1 hour</strong>
            </div>

            <p>If the button doesn't work, copy and paste this link into your browser:</p>
            <p style="background: white; padding: 15px; border-radius: 4px; word-break: break-all; font-family: monospace; font-size: 12px;">
                {reset_link}
            </p>

            <p style="margin-top: 30px; color: #666;">
                If you didn't request this password reset, please ignore this email. Your password will remain unchanged.
            </p>
        </div>
        <div class="footer">
            <p>© 2026 IntelliNews - AI-Powered Intelligence</p>
            <p>This is an automated email, please do not reply.</p>
        </div>
    </div>
</body>
</html>
            """

            # Send email using Resend API
            params = {
                "from": self.from_email,
                "to": [to_email],
                "subject": subject,
                "html": html_content,
            }

            email = resend.Emails.send(params)
            print(f"[Email] Password reset email sent to {to_email} (Resend ID: {email.get('id', 'N/A')})")
            return True

        except Exception as e:
            print(f"[Email] Failed to send password reset email: {e}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")
            return False


# Global instance
email_service = EmailService()
