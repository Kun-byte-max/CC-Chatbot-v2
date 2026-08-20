"""
backend/recommendation package initialization.
Exports RecommendationEngine, SkillMatcher, ExperienceMatcher, LocationMatcher, SalaryMatcher, TitleMatcher, and key models.
"""

from backend.recommendation.recommendation_engine import RecommendationEngine
from backend.recommendation.skill_matcher import SkillMatcher
from backend.recommendation.experience_matcher import ExperienceMatcher
from backend.recommendation.location_matcher import LocationMatcher
from backend.recommendation.salary_matcher import SalaryMatcher
from backend.recommendation.title_matcher import TitleMatcher
from backend.recommendation.score_calculator import ScoreCalculator
from backend.recommendation.explanation_generator import ExplanationGenerator
from backend.recommendation.models import (
    CandidateProfile,
    JobProfile,
    RecommendationResult,
    MatchBreakdown,
    SkillMatchResult,
    ExperienceMatchResult,
    LocationMatchResult,
    SalaryMatchResult,
    TitleMatchResult,
    ScoreResult,
    ExplanationResult,
)

__all__ = [
    "RecommendationEngine",
    "ScoreCalculator",
    "ExplanationGenerator",
    "SkillMatcher",
    "ExperienceMatcher",
    "LocationMatcher",
    "SalaryMatcher",
    "TitleMatcher",
    "CandidateProfile",
    "JobProfile",
    "RecommendationResult",
    "MatchBreakdown",
    "SkillMatchResult",
    "ExperienceMatchResult",
    "LocationMatchResult",
    "SalaryMatchResult",
    "TitleMatchResult",
    "ScoreResult",
    "ExplanationResult",
]


