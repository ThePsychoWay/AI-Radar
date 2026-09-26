"""
Processors module — Data processing and aggregation.
"""

from app.processors.data_layer import UnifiedDataLayer, UnifiedArticle, DeduplicationStrategy
from app.processors.deduplication import DeduplicationEngine, DuplicateCandidate, SimilarityMetric

__all__ = [
    "UnifiedDataLayer",
    "UnifiedArticle",
    "DeduplicationStrategy",
    "DeduplicationEngine",
    "DuplicateCandidate",
    "SimilarityMetric",
]
