"""
explanation_generator.py — Version 1 ExplanationGenerator implementation.
Converts matcher results and ScoreResult into human-readable explanation summaries, strengths, weaknesses, and structured RecommendationReason items.
"""

from typing import List, Optional, Dict, Any
try:
    from backend.recommendation.models import (
        ExplanationResult,
        RecommendationReason,
        ScoreResult,
        SkillMatchResult,
        ExperienceMatchResult,
        LocationMatchResult,
        SalaryMatchResult,
        TitleMatchResult,
    )
except ModuleNotFoundError:
    from recommendation.models import (  # type: ignore
        ExplanationResult,
        RecommendationReason,
        ScoreResult,
        SkillMatchResult,
        ExperienceMatchResult,
        LocationMatchResult,
        SalaryMatchResult,
        TitleMatchResult,
    )


def _format_skills_list(skills: List[str]) -> str:
    """Formats a list of skill strings naturally with 'and' for grammar."""
    if not skills:
        return ""
    clean = [str(s).strip() for s in skills if s]
    if len(clean) == 1:
        return clean[0]
    if len(clean) == 2:
        return f"{clean[0]} and {clean[1]}"
    return f"{', '.join(clean[:-1])}, and {clean[-1]}"


def _format_years(years: float) -> str:
    """Formats floating-point or integer experience years cleanly into singular or plural."""
    val = int(years) if isinstance(years, (int, float)) and float(years).is_integer() else round(float(years), 1)
    if val == 1:
        return "1 year"
    return f"{val} years"


class ExplanationGenerator:
    """
    Generates human-readable match explanation summaries, strengths, weaknesses,
    and structured RecommendationReason items.
    """

    SUMMARY_MAPPINGS = {
        "Excellent Match": "This job is an excellent match for your profile.",
        "Very Strong Match": "This job closely matches your profile with only minor gaps.",
        "Good Match": "This job is a good match for your profile.",
        "Fair Match": "This job partially matches your profile.",
        "Weak Match": "This job has several gaps compared to your profile.",
        "Not Recommended": "This job currently does not sufficiently match your profile.",
    }

    def generate_explanation(
        self,
        score_result: ScoreResult,
        skill_result: SkillMatchResult,
        experience_result: ExperienceMatchResult,
        location_result: LocationMatchResult,
        salary_result: SalaryMatchResult,
        title_result: TitleMatchResult,
    ) -> ExplanationResult:
        """
        Interprets MatchResult objects and ScoreResult to build an ExplanationResult,
        constructing both recommendation_explanation (summary string) and recommendation_reasons
        in a single, unified function invocation.
        """
        match_results = {
            "score_result": score_result,
            "skill_result": skill_result,
            "experience_result": experience_result,
            "location_result": location_result,
            "salary_result": salary_result,
            "title_result": title_result,
        }
        for name, res in match_results.items():
            if res is None:
                raise ValueError(f"Argument '{name}' cannot be None.")

        summary = self.SUMMARY_MAPPINGS.get(
            score_result.recommendation_level,
            "Match evaluation completed.",
        )

        strengths: List[str] = []
        weaknesses: List[str] = []
        reasons: List[RecommendationReason] = []

        # 1. Skill Matcher Evidence
        matched_skills = skill_result.matched_skills or []
        missing_skills = skill_result.missing_skills or []

        if matched_skills:
            formatted_matched = _format_skills_list(matched_skills)
            strengths.append(f"Matched skills: {', '.join(matched_skills)}")
            skill_noun = "skill" if len(matched_skills) == 1 else "skills"
            skill_verb = "matches" if len(matched_skills) == 1 else "match"
            reasons.append(RecommendationReason(
                type="skill",
                label="Skills",
                message=f"Your {formatted_matched} {skill_noun} {skill_verb} this job.",
                evidence={"matched_skills": list(matched_skills)}
            ))
        if missing_skills:
            weaknesses.append(f"Missing skills: {', '.join(missing_skills)}")

        # 2. Experience Matcher Evidence
        cand_exp = getattr(experience_result, "candidate_experience", 0.0) or 0.0
        req_exp = getattr(experience_result, "required_experience", 0.0) or 0.0
        meets_exp = getattr(experience_result, "meets_requirement", False)

        if meets_exp or experience_result.score >= 70.0:
            strengths.append("Meets experience requirement.")
            cand_exp_str = _format_years(cand_exp)
            req_exp_str = _format_years(req_exp)
            exp_verb = "matches" if cand_exp == 1 else "match"
            reasons.append(RecommendationReason(
                type="experience",
                label="Experience",
                message=f"Your {cand_exp_str} of experience {exp_verb} the {req_exp_str} required for this role.",
                evidence={
                    "candidate_experience": float(cand_exp),
                    "required_experience": float(req_exp)
                }
            ))
        else:
            weaknesses.append("Experience is below the required level.")

        # 3. Location Matcher Evidence (No hallucinated preferred location!)
        work_mode = getattr(location_result, "work_mode", "") or ""
        match_level = getattr(location_result, "match_level", "") or ""
        job_city = getattr(location_result, "job_city", None) or getattr(location_result, "candidate_city", None)

        if work_mode == "Remote" or match_level == "Remote":
            strengths.append("Eligible for remote work.")
            reasons.append(RecommendationReason(
                type="location",
                label="Location",
                message="This job offers a Remote work mode.",
                evidence={
                    "work_mode": work_mode,
                    "match_level": match_level
                }
            ))
        elif match_level in ("Exact City", "Exact"):
            city_name = job_city or "your city"
            strengths.append("Located in the same city.")
            reasons.append(RecommendationReason(
                type="location",
                label="Location",
                message=f"This job is located in {city_name}, matching your location.",
                evidence={
                    "job_city": job_city,
                    "match_level": match_level
                }
            ))
        elif match_level in ("State Match", "Country Match", "State", "Country"):
            strengths.append("Located in compatible region.")
            city_name = job_city or "a compatible region"
            reasons.append(RecommendationReason(
                type="location",
                label="Location",
                message=f"This job is located in {city_name}, matching your region.",
                evidence={
                    "job_city": job_city,
                    "match_level": match_level
                }
            ))
        elif match_level == "Different Country" or location_result.score < 50.0:
            weaknesses.append("Candidate is located in another country.")
        else:
            weaknesses.append("Location requirement is not fully satisfied.")

        # 4. Salary Matcher Evidence
        meets_sal = getattr(salary_result, "meets_expectation", False)
        if meets_sal or salary_result.score >= 70.0:
            strengths.append("Salary expectations are satisfied.")
            reasons.append(RecommendationReason(
                type="salary",
                label="Salary",
                message="The offered salary satisfies your expectations.",
                evidence={"meets_expectation": bool(meets_sal)}
            ))
        else:
            weaknesses.append("Offered salary is below the expected salary.")

        # 5. Title Matcher Evidence
        title_match_level = getattr(title_result, "match_level", "") or ""
        matched_kw = getattr(title_result, "matched_keywords", []) or []
        job_title_name = getattr(title_result, "job_title", None) or "the required role"

        if title_match_level in ("Exact Match", "Exact") or title_result.score >= 95.0:
            strengths.append("Job title matches exactly.")
            reasons.append(RecommendationReason(
                type="title",
                label="Role Match",
                message=f"Your profile title matches {job_title_name} exactly.",
                evidence={
                    "job_title": job_title_name,
                    "match_level": title_match_level
                }
            ))
        elif title_match_level in ("High Match", "High", "Medium Match", "Medium") or title_result.score >= 70.0:
            strengths.append("Job title closely matches candidate profile.")
            reasons.append(RecommendationReason(
                type="title",
                label="Role Match",
                message=f"Your profile closely matches the {job_title_name} role.",
                evidence={
                    "job_title": job_title_name,
                    "match_level": title_match_level
                }
            ))
        else:
            weaknesses.append("Current job title differs significantly from the required role.")

        # Engine Eligibility Fallback Rule:
        # If no specific matcher reason qualified, but job meets engine eligibility (recommendation_level != 'Not Recommended')
        if not reasons and score_result.recommendation_level != "Not Recommended":
            rec_level_str = score_result.recommendation_level.lower()
            reasons.append(RecommendationReason(
                type="overall",
                label="Overall Fit",
                message=f"This role is a {rec_level_str} overall for your profile.",
                evidence={"overall_score": float(score_result.overall_score)}
            ))

        # Build full human-readable paragraph summary for Chatbot answers
        if reasons:
            paragraph_parts = [r.message for r in reasons]
            full_explanation_text = " ".join(paragraph_parts)
        else:
            full_explanation_text = summary

        return ExplanationResult(
            summary=full_explanation_text,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendation_level=score_result.recommendation_level,
            overall_score=score_result.overall_score,
            recommendation_reasons=reasons,
        )
