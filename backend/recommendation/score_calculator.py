"""
score_calculator.py — Version 1 ScoreCalculator implementation.
Combines outputs of five matchers into one weighted recommendation score.
"""

from backend.recommendation.models import ScoreResult


class ScoreCalculator:
    """
    Combines individual component match scores into a final weighted recommendation score.
    """

    WEIGHT_SKILL: float = 0.40
    WEIGHT_EXPERIENCE: float = 0.20
    WEIGHT_TITLE: float = 0.15
    WEIGHT_SALARY: float = 0.15
    WEIGHT_LOCATION: float = 0.10

    def __init__(self) -> None:
        """Initialize ScoreCalculator and verify weight sum."""
        total_weight = (
            self.WEIGHT_SKILL
            + self.WEIGHT_EXPERIENCE
            + self.WEIGHT_TITLE
            + self.WEIGHT_SALARY
            + self.WEIGHT_LOCATION
        )
        if round(total_weight, 5) != 1.0:
            raise ValueError("Component weights must sum to exactly 1.0.")

    def _determine_recommendation_level(self, score: float) -> str:
        """Determines string recommendation level from overall score."""
        if score >= 90.0:
            return "Excellent Match"
        elif score >= 80.0:
            return "Very Strong Match"
        elif score >= 70.0:
            return "Good Match"
        elif score >= 60.0:
            return "Fair Match"
        elif score >= 50.0:
            return "Weak Match"
        else:
            return "Not Recommended"

    def calculate_score(
        self,
        skill_result,
        experience_result,
        location_result,
        salary_result,
        title_result,
    ) -> ScoreResult:
        """
        Calculates weighted composite score and recommendation level from MatchResult objects.
        """
        match_results = {
            "skill_result": skill_result,
            "experience_result": experience_result,
            "location_result": location_result,
            "salary_result": salary_result,
            "title_result": title_result,
        }

        for name, result in match_results.items():
            if result is None:
                raise ValueError(f"Match result '{name}' cannot be None.")

        skill_score = float(skill_result.score)
        experience_score = float(experience_result.score)
        location_score = float(location_result.score)
        salary_score = float(salary_result.score)
        title_score = float(title_result.score)

        raw_overall = (
            (skill_score * self.WEIGHT_SKILL)
            + (experience_score * self.WEIGHT_EXPERIENCE)
            + (title_score * self.WEIGHT_TITLE)
            + (salary_score * self.WEIGHT_SALARY)
            + (location_score * self.WEIGHT_LOCATION)
        )

        overall_score = round(raw_overall, 2)
        rec_level = self._determine_recommendation_level(overall_score)

        return ScoreResult(
            overall_score=overall_score,
            recommendation_level=rec_level,
            skill_score=round(skill_score, 2),
            experience_score=round(experience_score, 2),
            location_score=round(location_score, 2),
            salary_score=round(salary_score, 2),
            title_score=round(title_score, 2),
            weight_skill=round(self.WEIGHT_SKILL, 2),
            weight_experience=round(self.WEIGHT_EXPERIENCE, 2),
            weight_location=round(self.WEIGHT_LOCATION, 2),
            weight_salary=round(self.WEIGHT_SALARY, 2),
            weight_title=round(self.WEIGHT_TITLE, 2),
        )
