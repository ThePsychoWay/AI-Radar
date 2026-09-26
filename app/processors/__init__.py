"""
Processors module — Data processing and aggregation.
"""

from app.processors.data_layer import UnifiedDataLayer, UnifiedArticle, DeduplicationStrategy
from app.processors.deduplication import DeduplicationEngine, DuplicateCandidate, SimilarityMetric
from app.processors.verification import VerificationEngine, VerificationScore, QualityLevel, SourceReliability
from app.processors.importance import ImportanceRankingEngine, ImportanceScore, ImportanceLevel
from app.processors.personalization import (
    PersonalizationEngine,
    UserProfile,
    InterestProfile,
    PreferenceLevel,
    InteractionType,
)

__all__ = [
    "UnifiedDataLayer",
    "UnifiedArticle",
    "DeduplicationStrategy",
    "DeduplicationEngine",
    "DuplicateCandidate",
    "SimilarityMetric",
    "VerificationEngine",
    "VerificationScore",
    "QualityLevel",
    "SourceReliability",
    "ImportanceRankingEngine",
    "ImportanceScore",
    "ImportanceLevel",
    "PersonalizationEngine",
    "UserProfile",
    "InterestProfile",
    "PreferenceLevel",
    "InteractionType",
]
