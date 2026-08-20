"""
recommendation_service.py — Re-exports RecommendationService from backend.recommendation.recommendation_service.
"""

from backend.recommendation.recommendation_service import (
    RecommendationService,
    recommendation_service,
)

__all__ = ["RecommendationService", "recommendation_service"]
