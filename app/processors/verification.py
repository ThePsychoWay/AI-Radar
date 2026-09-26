"""
Verification Engine — Data quality scoring, freshness assessment, source reliability.

Evaluates:
- Article completeness (required fields)
- Content quality (length, readability)
- Source reliability (known/trusted sources)
- Data freshness (publication date recency)
- URL validity and accessibility
- Duplicate likelihood scoring
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import re
from urllib.parse import urlparse

from app.collectors.rss_collector import Article

logger = logging.getLogger(__name__)


class QualityLevel(Enum):
    """Quality assessment levels."""
    EXCELLENT = "excellent"  # 0.9-1.0
    GOOD = "good"  # 0.7-0.89
    ACCEPTABLE = "acceptable"  # 0.5-0.69
    POOR = "poor"  # 0.3-0.49
    REJECTED = "rejected"  # <0.3


class SourceReliability(Enum):
    """Source reliability classification."""
    HIGHLY_TRUSTED = "highly_trusted"  # Academic, official, major outlets
    TRUSTED = "trusted"  # Reputable tech blogs, news sites
    MODERATE = "moderate"  # Community-driven (HN, Reddit), lesser-known blogs
    UNVERIFIED = "unverified"  # New or unknown sources
    SUSPICIOUS = "suspicious"  # Spam patterns or known unreliable


@dataclass
class VerificationScore:
    """Complete verification assessment."""

    article: Article
    overall_score: float  # 0-1, aggregate quality
    quality_level: QualityLevel

    # Component scores (0-1)
    completeness_score: float  # Required fields present
    content_quality_score: float  # Length, structure, readability
    freshness_score: float  # How recent is the publication
    source_reliability_score: float  # Source trust level
    url_validity_score: float  # URL format and accessibility
    duplicate_risk_score: float  # Risk of being duplicate (0=no risk, 1=high risk)

    # Metadata
    issues: List[str] = None  # List of quality issues found
    warnings: List[str] = None  # Non-critical warnings
    source_trust_level: SourceReliability = SourceReliability.UNVERIFIED

    def __post_init__(self):
        if self.issues is None:
            self.issues = []
        if self.warnings is None:
            self.warnings = []


class VerificationEngine:
    """Advanced data quality and verification."""

    def __init__(
        self,
        min_quality_threshold: float = 0.5,
        freshness_days: int = 30,
    ):
        """
        Initialize verification engine.

        Args:
            min_quality_threshold: Minimum acceptable quality score.
            freshness_days: Days to consider data "fresh".
        """
        self.min_quality_threshold = min_quality_threshold
        self.freshness_days = freshness_days

        # Known trusted sources
        self.highly_trusted_domains = {
            "arxiv.org",
            "nature.com",
            "science.org",
            "ieee.org",
            "acm.org",
            "springer.com",
            "openreview.net",
            "nytimes.com",
            "bbc.com",
            "reuters.com",
        }

        self.trusted_domains = {
            "github.com",
            "medium.com",
            "dev.to",
            "techcrunch.com",
            "theverge.com",
            "arstechnica.com",
            "dzone.com",
            "infoq.com",
            "semanticscholar.org",
        }

        self.community_domains = {
            "news.ycombinator.com",
            "reddit.com",
            "twitter.com",
            "linkedin.com",
        }

    def verify_article(self, article: Article) -> VerificationScore:
        """
        Comprehensively verify a single article.

        Returns:
            VerificationScore with detailed assessment.
        """
        issues = []
        warnings = []

        # Check completeness
        completeness_score = self._check_completeness(article, issues)

        # Check content quality
        content_quality_score = self._check_content_quality(article, issues, warnings)

        # Check freshness
        freshness_score = self._check_freshness(article, warnings)

        # Assess source reliability
        source_reliability_score, source_trust_level = self._assess_source_reliability(
            article, warnings
        )

        # Check URL validity
        url_validity_score = self._check_url_validity(article, warnings)

        # Calculate duplicate risk
        duplicate_risk_score = self._calculate_duplicate_risk(article)

        # Calculate overall score (weighted)
        overall_score = (
            completeness_score * 0.15
            + content_quality_score * 0.25
            + freshness_score * 0.15
            + source_reliability_score * 0.25
            + url_validity_score * 0.10
            + (1.0 - duplicate_risk_score) * 0.10  # Lower is better for duplicates
        )

        # Determine quality level
        if overall_score >= 0.9:
            quality_level = QualityLevel.EXCELLENT
        elif overall_score >= 0.7:
            quality_level = QualityLevel.GOOD
        elif overall_score >= 0.5:
            quality_level = QualityLevel.ACCEPTABLE
        elif overall_score >= 0.3:
            quality_level = QualityLevel.POOR
        else:
            quality_level = QualityLevel.REJECTED

        return VerificationScore(
            article=article,
            overall_score=overall_score,
            quality_level=quality_level,
            completeness_score=completeness_score,
            content_quality_score=content_quality_score,
            freshness_score=freshness_score,
            source_reliability_score=source_reliability_score,
            url_validity_score=url_validity_score,
            duplicate_risk_score=duplicate_risk_score,
            issues=issues,
            warnings=warnings,
            source_trust_level=source_trust_level,
        )

    def _check_completeness(self, article: Article, issues: List[str]) -> float:
        """Check if required fields are present."""
        score = 1.0
        missing = []

        title = getattr(article, 'title', None) or ""
        if not title or len(str(title).strip()) < 3:
            missing.append("title")
            score -= 0.2

        url = getattr(article, 'url', None) or ""
        if not url:
            missing.append("url")
            score -= 0.2

        summary = getattr(article, 'summary', None) or ""
        if not summary or len(str(summary).strip()) < 10:
            missing.append("summary")
            score -= 0.15

        source = getattr(article, 'source', None) or ""
        if not source:
            missing.append("source")
            score -= 0.15

        published_at = getattr(article, 'published_at', None)
        if not published_at:
            missing.append("published_at")
            score -= 0.15

        if missing:
            issues.append(f"Missing fields: {', '.join(missing)}")

        return max(0.0, score)

    def _check_content_quality(
        self, article: Article, issues: List[str], warnings: List[str]
    ) -> float:
        """Assess content quality based on length and structure."""
        score = 1.0

        # Handle None values
        title = getattr(article, 'title', None) or ""
        summary = getattr(article, 'summary', None) or ""

        # Check title quality
        title_len = len(str(title).strip())
        if title_len < 5:
            issues.append("Title too short (< 5 chars)")
            score -= 0.2
        elif title_len > 200:
            warnings.append("Title very long (> 200 chars)")
            score -= 0.05

        # Check summary quality
        summary_len = len(str(summary).strip())
        if summary_len < 20:
            issues.append("Summary too short (< 20 chars)")
            score -= 0.2
        elif summary_len > 50000:
            warnings.append("Summary extremely long (> 50k chars)")
            score -= 0.05

        # Check for spam patterns
        spam_patterns = [
            r"viagra|cialis|casino|lottery|click here|buy now",
            r"make \$|earn money|work from home",
            r"\.ru$|\.xyz$|\.tk$",  # Suspicious TLDs
        ]

        content = f"{str(title)} {str(summary)}".lower()
        for pattern in spam_patterns:
            if re.search(pattern, content):
                issues.append("Spam pattern detected")
                score = 0.0  # Automatic fail for spam content
                break

        # Check for minimal effort (too short content)
        if summary_len < 50:
            warnings.append("Very brief summary (< 50 chars)")
            score -= 0.1

        return max(0.0, score)

    def _check_freshness(self, article: Article, warnings: List[str]) -> float:
        """Assess how recent the article is."""
        published_at = getattr(article, 'published_at', None)
        if not published_at:
            return 0.5  # Unknown freshness

        now = datetime.now(published_at.tzinfo) if published_at.tzinfo else datetime.now()
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=None)
            now = datetime.now()

        age_days = (now - published_at).days

        if age_days < 0:
            warnings.append("Future publication date")
            return 0.5

        if age_days == 0:
            return 1.0
        elif age_days <= 7:
            return 0.95
        elif age_days <= self.freshness_days:
            return 0.9 - (age_days / self.freshness_days) * 0.4
        elif age_days <= self.freshness_days * 2:
            return 0.5 - (age_days / (self.freshness_days * 2)) * 0.2
        else:
            warnings.append(f"Article is {age_days} days old (stale)")
            return 0.2

    def _assess_source_reliability(
        self, article: Article, warnings: List[str]
    ) -> Tuple[float, SourceReliability]:
        """Assess source trustworthiness."""
        url = getattr(article, 'url', None) or ""
        if not url:
            return 0.4, SourceReliability.UNVERIFIED

        try:
            domain = urlparse(str(url)).netloc.lower()
            domain = domain.replace("www.", "")
        except Exception:
            return 0.3, SourceReliability.UNVERIFIED

        # Check domain reputation
        if domain in self.highly_trusted_domains:
            return 0.95, SourceReliability.HIGHLY_TRUSTED

        if domain in self.trusted_domains:
            return 0.85, SourceReliability.TRUSTED

        if domain in self.community_domains:
            return 0.7, SourceReliability.MODERATE

        # Heuristic checks for unknown domains - check suspicious TLD first
        if re.search(r"\.(ru|xyz|tk|ml|ga)$", domain):
            warnings.append("Suspicious TLD")
            return 0.2, SourceReliability.SUSPICIOUS  # Reduced from 0.4

        if re.match(r"^[a-z0-9\-]+\d+\.[a-z]+$", domain):
            warnings.append("Suspicious domain pattern (random-hash format)")
            return 0.2, SourceReliability.SUSPICIOUS  # Reduced from 0.3

        # Default for unknown but reasonable domains
        if "." in domain and len(domain) > 4:
            return 0.6, SourceReliability.UNVERIFIED

        return 0.3, SourceReliability.SUSPICIOUS

    def _check_url_validity(self, article: Article, warnings: List[str]) -> float:
        """Check URL format and basic validity."""
        url_str = getattr(article, 'url', None) or ""
        if not url_str:
            return 0.0

        url = str(url_str).lower()

        # Check basic URL format
        if not re.match(r"^https?://", url):
            warnings.append("URL missing http/https scheme")
            return 0.4

        # Check for suspicious URL patterns
        if "redirect" in url or "tracking" in url:
            warnings.append("Redirect/tracking URL detected")
            return 0.7

        # Check for valid domain structure
        try:
            parsed = urlparse(url)
            if not parsed.netloc or "." not in parsed.netloc:
                warnings.append("Invalid URL structure")
                return 0.3
        except Exception:
            warnings.append("URL parsing error")
            return 0.3

        # Check for excessive query parameters (spam indicator)
        if url.count("=") > 5:
            warnings.append("Excessive query parameters")
            return 0.6

        return 0.9

    def _calculate_duplicate_risk(self, article: Article) -> float:
        """Calculate likelihood of being a duplicate (0=no risk, 1=high risk)."""
        risk = 0.0

        # Handle None values
        title = getattr(article, 'title', None) or ""
        summary = getattr(article, 'summary', None) or ""

        # Empty fields increase risk
        if not title or len(str(title).strip()) < 5:
            risk += 0.3
        if not summary or len(str(summary).strip()) < 20:
            risk += 0.2

        # Generic titles increase risk
        generic_titles = [
            "update", "news", "breaking", "latest",
            "announcement", "release", "new", "today"
        ]
        title_lower = str(title).lower()
        if any(title_lower.startswith(g) for g in generic_titles):
            risk += 0.15

        # Very short summary increases risk
        if len(str(summary).strip()) < 50:
            risk += 0.1

        return min(1.0, risk)

    def verify_batch(self, articles: List[Article]) -> List[VerificationScore]:
        """
        Verify multiple articles.

        Returns:
            List of VerificationScore objects.
        """
        return [self.verify_article(article) for article in articles]

    def filter_by_quality(
        self, articles: List[Article], min_quality: Optional[float] = None
    ) -> Tuple[List[Article], List[VerificationScore]]:
        """
        Filter articles by quality threshold.

        Returns:
            (passing_articles, verification_scores_for_all)
        """
        threshold = min_quality or self.min_quality_threshold
        scores = self.verify_batch(articles)

        passing = [
            score.article for score in scores if score.overall_score >= threshold
        ]

        return passing, scores

    def get_statistics(self, scores: List[VerificationScore]) -> Dict:
        """Generate statistics about verification results."""
        if not scores:
            return {
                "total_articles": 0,
                "excellent": 0,
                "good": 0,
                "acceptable": 0,
                "poor": 0,
                "rejected": 0,
                "average_score": 0.0,
                "average_completeness": 0.0,
                "average_content_quality": 0.0,
                "average_freshness": 0.0,
                "average_source_reliability": 0.0,
                "most_common_issue": None,
                "most_common_warning": None,
                "source_reliability_breakdown": {},
            }

        level_counts = {
            QualityLevel.EXCELLENT: 0,
            QualityLevel.GOOD: 0,
            QualityLevel.ACCEPTABLE: 0,
            QualityLevel.POOR: 0,
            QualityLevel.REJECTED: 0,
        }

        for score in scores:
            level_counts[score.quality_level] += 1

        # Count issues and warnings
        all_issues = []
        all_warnings = []
        for score in scores:
            all_issues.extend(score.issues)
            all_warnings.extend(score.warnings)

        # Source reliability breakdown
        reliability_counts = {}
        for score in scores:
            trust = score.source_trust_level.value
            reliability_counts[trust] = reliability_counts.get(trust, 0) + 1

        def most_common(items):
            if not items:
                return None
            from collections import Counter
            return Counter(items).most_common(1)[0][0]

        return {
            "total_articles": len(scores),
            "excellent": level_counts[QualityLevel.EXCELLENT],
            "good": level_counts[QualityLevel.GOOD],
            "acceptable": level_counts[QualityLevel.ACCEPTABLE],
            "poor": level_counts[QualityLevel.POOR],
            "rejected": level_counts[QualityLevel.REJECTED],
            "average_score": sum(s.overall_score for s in scores) / len(scores),
            "average_completeness": sum(s.completeness_score for s in scores)
            / len(scores),
            "average_content_quality": sum(s.content_quality_score for s in scores)
            / len(scores),
            "average_freshness": sum(s.freshness_score for s in scores) / len(scores),
            "average_source_reliability": sum(s.source_reliability_score for s in scores)
            / len(scores),
            "most_common_issue": most_common(all_issues),
            "most_common_warning": most_common(all_warnings),
            "source_reliability_breakdown": reliability_counts,
        }

    def generate_report(self, score: VerificationScore) -> str:
        """Generate human-readable verification report."""
        lines = [
            f"\n{'='*60}",
            f"Article: {score.article.title[:60]}...",
            f"{'='*60}",
            f"\nQuality Level: {score.quality_level.value.upper()}",
            f"Overall Score: {score.overall_score:.2%}",
            f"\nComponent Scores:",
            f"  • Completeness:        {score.completeness_score:.1%}",
            f"  • Content Quality:     {score.content_quality_score:.1%}",
            f"  • Freshness:           {score.freshness_score:.1%}",
            f"  • Source Reliability:  {score.source_reliability_score:.1%}",
            f"  • URL Validity:        {score.url_validity_score:.1%}",
            f"  • Duplicate Risk:      {score.duplicate_risk_score:.1%}",
        ]

        if score.issues:
            lines.append(f"\n🚨 Issues:")
            for issue in score.issues:
                lines.append(f"  • {issue}")

        if score.warnings:
            lines.append(f"\n⚠️  Warnings:")
            for warning in score.warnings:
                lines.append(f"  • {warning}")

        lines.append(f"\nSource Trust: {score.source_trust_level.value}")
        lines.append(f"{'='*60}\n")

        return "\n".join(lines)


def main():
    """CLI example."""
    logging.basicConfig(level=logging.INFO)
    print("Verification Engine initialized")
    print("Quality Levels: excellent, good, acceptable, poor, rejected")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
