"""
Daily Digest Generator — Create formatted digests for delivery.

Generates:
- Email digest (HTML + plain text versions)
- Digest categorization (sections by type, interest, importance)
- Newsletter formatting with metadata
- Read time estimates
- Preference management links
- Unsubscribe handling
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
import html
from urllib.parse import urlencode

from app.analyzers.decision_engine import Recommendation, RecommendationType
from app.collectors.rss_collector import Article

logger = logging.getLogger(__name__)


class DigestFormat(Enum):
    """Digest output format."""
    EMAIL_HTML = "email_html"  # HTML email format
    EMAIL_TEXT = "email_text"  # Plain text email format
    WEB = "web"  # Web-friendly HTML
    MARKDOWN = "markdown"  # Markdown format
    JSON = "json"  # JSON structure


@dataclass
class DigestMetadata:
    """Metadata about a digest."""

    user_id: str
    digest_date: datetime
    timezone: str = "UTC"
    recipient_email: Optional[str] = None
    digest_id: str = ""  # Unique identifier for tracking
    total_recommendations: int = 0
    total_read_time_minutes: int = 0
    critical_count: int = 0
    featured_count: int = 0
    relevant_count: int = 0
    discover_count: int = 0
    categories: List[str] = field(default_factory=list)
    top_interests: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Generate digest ID if not provided."""
        if not self.digest_id:
            timestamp = self.digest_date.strftime("%Y%m%d%H%M%S")
            self.digest_id = f"digest_{self.user_id}_{timestamp}"


@dataclass
class DigestSection:
    """A section within a digest."""

    title: str
    description: str
    recommendations: List[Recommendation] = field(default_factory=list)
    total_read_time: int = 0  # Minutes
    priority: int = 0  # Lower = higher priority (0 = top)


class DigestGenerator:
    """Generate formatted digests from recommendations."""

    def __init__(
        self,
        user_id: str,
        user_email: Optional[str] = None,
        base_url: str = "https://radar.local",
    ):
        """
        Initialize digest generator.

        Args:
            user_id: User identifier.
            user_email: User email for digest delivery.
            base_url: Base URL for tracking/preference links.
        """
        self.user_id = user_id
        self.user_email = user_email
        self.base_url = base_url

    def organize_by_type(
        self,
        recommendations: List[Recommendation],
    ) -> Dict[RecommendationType, List[Recommendation]]:
        """
        Organize recommendations by type.

        Returns:
            Dict mapping recommendation type to list of recommendations.
        """
        organized = {}

        for rec_type in RecommendationType:
            organized[rec_type] = [
                r for r in recommendations
                if r.recommendation_type == rec_type
            ]

        return organized

    def estimate_read_time(self, article: Article, words_per_minute: int = 200) -> int:
        """
        Estimate read time in minutes.

        Args:
            article: Article to estimate.
            words_per_minute: Reading speed assumption.

        Returns:
            Estimated read time in minutes (minimum 1).
        """
        if not article.summary:
            return 1

        # Simple word count estimate
        word_count = len(article.summary.split())

        # Add title word count
        if article.title:
            word_count += len(article.title.split())

        minutes = max(1, word_count // words_per_minute)
        return minutes

    def create_sections(
        self,
        recommendations: List[Recommendation],
    ) -> List[DigestSection]:
        """
        Create digest sections from recommendations.

        Returns:
            List of DigestSection objects.
        """
        sections = []

        # Critical section
        critical = [
            r for r in recommendations
            if r.recommendation_type == RecommendationType.CRITICAL
        ]
        if critical:
            total_time = sum(self.estimate_read_time(r.article) for r in critical)
            sections.append(
                DigestSection(
                    title="🔥 Critical — Must Read",
                    description="High-impact articles you shouldn't miss",
                    recommendations=critical,
                    total_read_time=total_time,
                    priority=0,
                )
            )

        # Featured section
        featured = [
            r for r in recommendations
            if r.recommendation_type == RecommendationType.FEATURED
        ]
        if featured:
            total_time = sum(self.estimate_read_time(r.article) for r in featured)
            sections.append(
                DigestSection(
                    title="⭐ Featured — Today's Highlights",
                    description="Important articles matching your interests",
                    recommendations=featured,
                    total_read_time=total_time,
                    priority=1,
                )
            )

        # Relevant section
        relevant = [
            r for r in recommendations
            if r.recommendation_type == RecommendationType.RELEVANT
        ]
        if relevant:
            total_time = sum(self.estimate_read_time(r.article) for r in relevant)
            sections.append(
                DigestSection(
                    title="📖 Relevant — Your Interests",
                    description="Content tailored to your interests",
                    recommendations=relevant,
                    total_read_time=total_time,
                    priority=2,
                )
            )

        # Discover section
        discover = [
            r for r in recommendations
            if r.recommendation_type == RecommendationType.DISCOVER
        ]
        if discover:
            total_time = sum(self.estimate_read_time(r.article) for r in discover)
            sections.append(
                DigestSection(
                    title="🔎 Discover — Explore",
                    description="Interesting content you might enjoy",
                    recommendations=discover,
                    total_read_time=total_time,
                    priority=3,
                )
            )

        return sections

    def generate_metadata(
        self,
        recommendations: List[Recommendation],
        digest_date: Optional[datetime] = None,
    ) -> DigestMetadata:
        """Generate digest metadata."""
        if digest_date is None:
            digest_date = datetime.now(timezone.utc)

        organized = self.organize_by_type(recommendations)
        total_read_time = sum(
            self.estimate_read_time(r.article)
            for r in recommendations
        )

        categories = set()
        for rec in recommendations:
            if rec.article.category:
                categories.add(rec.article.category)

        top_interests = []
        for rec in recommendations:
            if rec.matched_interests:
                top_interests.extend(rec.matched_interests)

        # Count top interests
        interest_counts = {}
        for interest in top_interests:
            interest_counts[interest] = interest_counts.get(interest, 0) + 1

        top_interests = [
            interest for interest, _ in sorted(
                interest_counts.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:10]
        ]

        return DigestMetadata(
            user_id=self.user_id,
            digest_date=digest_date,
            recipient_email=self.user_email,
            total_recommendations=len(recommendations),
            total_read_time_minutes=total_read_time,
            critical_count=len(organized.get(RecommendationType.CRITICAL, [])),
            featured_count=len(organized.get(RecommendationType.FEATURED, [])),
            relevant_count=len(organized.get(RecommendationType.RELEVANT, [])),
            discover_count=len(organized.get(RecommendationType.DISCOVER, [])),
            categories=sorted(list(categories)),
            top_interests=top_interests,
        )

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return html.escape(text) if text else ""

    def _generate_article_html(
        self,
        rec: Recommendation,
        include_snippet: bool = True,
    ) -> str:
        """Generate HTML for single article."""
        article = rec.article
        read_time = self.estimate_read_time(article)

        # Build tracking URL
        tracking_params = {
            "user": self.user_id,
            "article": article.id,
            "source": article.source or "unknown",
            "action": "click",
        }
        tracking_url = f"{self.base_url}/track?{urlencode(tracking_params)}"

        html_str = f"""
        <div style="margin-bottom: 24px; border-left: 4px solid #2563eb; padding-left: 16px;">
            <h3 style="margin: 0 0 8px 0; font-size: 16px; font-weight: 600; color: #1f2937;">
                <a href="{self._escape_html(tracking_url)}" style="color: #2563eb; text-decoration: none;">
                    {self._escape_html(article.title)}
                </a>
            </h3>
            <p style="margin: 0 0 8px 0; font-size: 13px; color: #6b7280;">
                {self._escape_html(article.source or "Unknown")} • {read_time} min read
                {f' • By {self._escape_html(article.author)}' if article.author else ''}
            </p>
        """

        if include_snippet and rec.summary_snippet:
            html_str += f"""
            <p style="margin: 0 0 12px 0; font-size: 14px; color: #374151; line-height: 1.5;">
                {self._escape_html(rec.summary_snippet)}
            </p>
            """

        html_str += """
            <p style="margin: 0; font-size: 13px;">
                <a href="{url}" style="color: #2563eb; text-decoration: none; font-weight: 500;">Read Full Article →</a>
            </p>
        </div>
        """.format(url=self._escape_html(tracking_url))

        return html_str

    def generate_email_html(
        self,
        recommendations: List[Recommendation],
        metadata: Optional[DigestMetadata] = None,
    ) -> str:
        """
        Generate HTML email digest.

        Returns:
            Complete HTML email as string.
        """
        if metadata is None:
            metadata = self.generate_metadata(recommendations)

        sections = self.create_sections(recommendations)

        # Email header
        digest_date_str = metadata.digest_date.strftime("%B %d, %Y")

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    line-height: 1.6;
                    color: #1f2937;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .container {{
                    background-color: #ffffff;
                }}
                .header {{
                    border-bottom: 2px solid #e5e7eb;
                    padding-bottom: 24px;
                    margin-bottom: 24px;
                }}
                .header h1 {{
                    margin: 0 0 8px 0;
                    font-size: 24px;
                    font-weight: 700;
                    color: #1f2937;
                }}
                .header p {{
                    margin: 0;
                    font-size: 14px;
                    color: #6b7280;
                }}
                .section {{
                    margin-bottom: 32px;
                }}
                .section-header {{
                    font-size: 18px;
                    font-weight: 600;
                    margin-bottom: 12px;
                    color: #1f2937;
                }}
                .section-description {{
                    font-size: 14px;
                    color: #6b7280;
                    margin-bottom: 16px;
                }}
                .stats {{
                    background-color: #f3f4f6;
                    border-radius: 8px;
                    padding: 16px;
                    margin-bottom: 24px;
                    font-size: 14px;
                    color: #374151;
                }}
                .footer {{
                    border-top: 1px solid #e5e7eb;
                    padding-top: 20px;
                    margin-top: 32px;
                    font-size: 12px;
                    color: #6b7280;
                    text-align: center;
                }}
                .footer a {{
                    color: #2563eb;
                    text-decoration: none;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📰 Your AI Radar Digest</h1>
                    <p>{digest_date_str} • {metadata.total_recommendations} articles</p>
                </div>

                <div class="stats">
                    <strong>Today's Summary:</strong><br>
                    ⏱️ {metadata.total_read_time_minutes} min read time<br>
                    🔥 {metadata.critical_count} critical • ⭐ {metadata.featured_count} featured
                    {f'<br>📚 Top interests: {", ".join(metadata.top_interests[:3])}' if metadata.top_interests else ''}
                </div>
        """

        # Add sections
        for section in sections:
            html_content += f"""
                <div class="section">
                    <div class="section-header">{self._escape_html(section.title)}</div>
                    <div class="section-description">{self._escape_html(section.description)}</div>
            """

            for rec in section.recommendations:
                html_content += self._generate_article_html(rec)

            html_content += f"""
                    <p style="font-size: 13px; color: #6b7280; margin-top: 12px;">
                        {len(section.recommendations)} articles • {section.total_read_time} min read
                    </p>
                </div>
            """

        # Footer
        unsubscribe_params = {
            "user": self.user_id,
            "action": "unsubscribe",
            "digest_id": metadata.digest_id,
        }
        unsubscribe_url = f"{self.base_url}/preferences?{urlencode(unsubscribe_params)}"

        html_content += f"""
                <div class="footer">
                    <p>
                        <a href="{self._escape_html(self.base_url)}/digest/{metadata.digest_id}">View in Browser</a> •
                        <a href="{self._escape_html(unsubscribe_url)}">Manage Preferences</a>
                    </p>
                    <p style="margin-top: 12px;">
                        AI Radar — Your personalized intelligence system<br>
                        Digest ID: {metadata.digest_id}
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

        return html_content

    def generate_email_text(
        self,
        recommendations: List[Recommendation],
        metadata: Optional[DigestMetadata] = None,
    ) -> str:
        """
        Generate plain text email digest.

        Returns:
            Plain text email as string.
        """
        if metadata is None:
            metadata = self.generate_metadata(recommendations)

        sections = self.create_sections(recommendations)
        digest_date_str = metadata.digest_date.strftime("%B %d, %Y")

        text_content = f"""
╔═══════════════════════════════════════════════════════════════╗
║         📰 YOUR AI RADAR DIGEST - {digest_date_str}         ║
╚═══════════════════════════════════════════════════════════════╝

Summary
───────
Total Articles: {metadata.total_recommendations}
Total Read Time: {metadata.total_read_time_minutes} minutes
🔥 Critical: {metadata.critical_count} | ⭐ Featured: {metadata.featured_count}
📖 Relevant: {metadata.relevant_count} | 🔎 Discover: {metadata.discover_count}

Top Interests: {', '.join(metadata.top_interests[:5]) if metadata.top_interests else 'None'}

═══════════════════════════════════════════════════════════════
"""

        # Add sections
        for section in sections:
            text_content += f"\n{section.title}\n"
            text_content += "─" * 60 + "\n"
            text_content += f"{section.description}\n\n"

            for i, rec in enumerate(section.recommendations, 1):
                article = rec.article
                read_time = self.estimate_read_time(article)

                text_content += f"{i}. {article.title}\n"
                text_content += f"   Source: {article.source or 'Unknown'} • {read_time} min\n"
                if article.author:
                    text_content += f"   Author: {article.author}\n"
                if rec.summary_snippet:
                    text_content += f"   {rec.summary_snippet[:100]}...\n"
                text_content += f"   URL: {article.url}\n\n"

            text_content += f"({len(section.recommendations)} articles • {section.total_read_time} min read)\n"
            text_content += "─" * 60 + "\n"

        # Footer
        text_content += f"""
═══════════════════════════════════════════════════════════════

Manage Preferences: {self.base_url}/preferences
View Online: {self.base_url}/digest/{metadata.digest_id}

AI Radar — Your personalized intelligence system
Digest ID: {metadata.digest_id}
"""

        return text_content

    def generate_digest_json(
        self,
        recommendations: List[Recommendation],
        metadata: Optional[DigestMetadata] = None,
    ) -> Dict:
        """
        Generate digest as JSON structure.

        Returns:
            JSON-serializable dictionary.
        """
        if metadata is None:
            metadata = self.generate_metadata(recommendations)

        sections = self.create_sections(recommendations)

        sections_data = []
        for section in sections:
            articles_data = []
            for rec in section.recommendations:
                articles_data.append({
                    "id": rec.article.id,
                    "title": rec.article.title,
                    "url": rec.article.url,
                    "source": rec.article.source,
                    "author": rec.article.author,
                    "summary": rec.article.summary,
                    "published_at": rec.article.published_at.isoformat() if rec.article.published_at else None,
                    "category": rec.article.category,
                    "tags": rec.article.tags,
                    "recommendation_type": rec.recommendation_type.value,
                    "combined_score": rec.combined_score,
                    "read_time_minutes": self.estimate_read_time(rec.article),
                })

            sections_data.append({
                "title": section.title,
                "description": section.description,
                "articles": articles_data,
                "total_read_time": section.total_read_time,
            })

        return {
            "metadata": {
                "digest_id": metadata.digest_id,
                "user_id": metadata.user_id,
                "digest_date": metadata.digest_date.isoformat(),
                "total_recommendations": metadata.total_recommendations,
                "total_read_time_minutes": metadata.total_read_time_minutes,
                "critical_count": metadata.critical_count,
                "featured_count": metadata.featured_count,
                "relevant_count": metadata.relevant_count,
                "discover_count": metadata.discover_count,
                "categories": metadata.categories,
                "top_interests": metadata.top_interests,
            },
            "sections": sections_data,
        }

    def generate_digest(
        self,
        recommendations: List[Recommendation],
        format: DigestFormat = DigestFormat.EMAIL_HTML,
        metadata: Optional[DigestMetadata] = None,
    ) -> str:
        """
        Generate digest in specified format.

        Args:
            recommendations: List of recommendations.
            format: Output format.
            metadata: Pre-generated metadata (optional).

        Returns:
            Formatted digest as string (or JSON string for JSON format).
        """
        if format == DigestFormat.EMAIL_HTML:
            return self.generate_email_html(recommendations, metadata)

        elif format == DigestFormat.EMAIL_TEXT:
            return self.generate_email_text(recommendations, metadata)

        elif format == DigestFormat.JSON:
            import json
            return json.dumps(
                self.generate_digest_json(recommendations, metadata),
                indent=2,
                default=str,
            )

        else:
            # Default to HTML
            return self.generate_email_html(recommendations, metadata)


def main():
    """CLI example."""
    logging.basicConfig(level=logging.INFO)
    print("Daily Digest Generator initialized")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
