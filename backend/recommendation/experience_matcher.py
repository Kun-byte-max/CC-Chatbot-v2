"""
experience_matcher.py — Experience Matching Module for V1 Recommendation Engine.
"""

import re
from typing import Any, Optional
from backend.recommendation.models import CandidateProfile, ExperienceMatchResult, JobProfile


class ExperienceMatcher:
    """
    Evaluates candidate experience suitability against job requirements using V1 gap-penalty scoring.
    """

    def _normalize_experience(self, value: Any) -> float:
        """
        Normalizes any input value into a non-negative float representing years of experience.
        - Converts numeric types and numeric strings to float.
        - Treats None, empty strings, and invalid inputs as 0.0.
        - Converts negative values to 0.0.
        - Never raises exceptions.

        :param value: Input experience value (int, float, str, None, etc.).
        :return: Non-negative float experience in years.
        """
        if value is None:
            return 0.0

        try:
            if isinstance(value, (int, float)):
                num = float(value)
                return num if num > 0.0 else 0.0

            if isinstance(value, str):
                cleaned = value.strip()
                if not cleaned:
                    return 0.0
                try:
                    num = float(cleaned)
                    return num if num > 0.0 else 0.0
                except ValueError:
                    match = re.search(r"[-+]?\d*\.?\d+", cleaned)
                    if match:
                        num = float(match.group())
                        return num if num > 0.0 else 0.0
                    return 0.0

            num = float(value)
            return num if num > 0.0 else 0.0
        except Exception:
            return 0.0

    def _match_experience(
        self, candidate_exp: Any, required_exp: Any
    ) -> ExperienceMatchResult:
        """
        Internal evaluator calculating experience fit metrics and penalty scores.

        :param candidate_exp: Candidate experience value (int, float, str, etc.).
        :param required_exp: Required job experience value (int, float, str, etc.).
        :return: ExperienceMatchResult dataclass.
        """
        cand_exp = self._normalize_experience(candidate_exp)
        req_exp = self._normalize_experience(required_exp)

        # Freshers / Job requires 0 years OR Candidate meets/exceeds requirement
        if req_exp == 0.0 or cand_exp >= req_exp:
            return ExperienceMatchResult(
                score=100.0,
                candidate_experience=cand_exp,
                required_experience=req_exp,
                experience_gap=0.0,
                meets_requirement=True,
            )

        gap = round(req_exp - cand_exp, 2)

        if gap <= 1.0:
            score = 80.0
        elif gap <= 2.0:
            score = 60.0
        elif gap <= 3.0:
            score = 40.0
        else:
            score = 20.0

        return ExperienceMatchResult(
            score=score,
            candidate_experience=cand_exp,
            required_experience=req_exp,
            experience_gap=gap,
            meets_requirement=False,
        )

    def evaluate_profiles(
        self, candidate: Optional[CandidateProfile], job: Optional[JobProfile]
    ) -> ExperienceMatchResult:
        """
        Standardized public API to evaluate experience match between CandidateProfile and JobProfile.

        :param candidate: CandidateProfile dataclass instance or None.
        :param job: JobProfile dataclass instance or None.
        :return: ExperienceMatchResult dataclass instance.
        """
        cand_exp = candidate.experience_years if candidate else 0.0
        req_exp = job.required_experience_years if job else 0.0
        return self._match_experience(cand_exp, req_exp)
