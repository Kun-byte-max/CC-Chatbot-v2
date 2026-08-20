"""
formatters.py — Response formatter for recommendation results.
Formats RecommendationResult objects into candidate-facing chatbot responses.
"""

from typing import List, Optional
try:
    from backend.recommendation.models import RecommendationResult
except ModuleNotFoundError:
    from recommendation.models import RecommendationResult  # type: ignore


def format_recommendations_response(
    results: List[RecommendationResult],
    candidate_id: Optional[int] = None,
    candidate_exists: bool = True,
    profile_complete: bool = True,
    active_jobs_exist: bool = True
) -> str:
    """
    Formats recommendation engine results into structured chatbot response text.
    Handles error & edge cases according to Phase 11 specifications.
    """
    if not candidate_exists or candidate_id is None:
        return "No candidate profile found. Please log in or register to get job recommendations."

    if not profile_complete:
        return "Your profile is incomplete. Please update your skills and experience details to get personalized job recommendations."

    if not active_jobs_exist:
        return "No active jobs were found."

    if not results:
        return "No suitable jobs were found."

    lines = ["Here are your best matching jobs:\n"]
    divider = "-" * 50

    for res in results:
        job = res.title_result.job_title or "Job Title"
        # Extract job metadata from score_result / explanation_result
        exp_gen = res.explanation_result
        score_percent = int(round(res.overall_score * 100)) if res.overall_score <= 1.0 else int(round(res.overall_score))

        # Check job profile title & company if attached in raw details
        comp_name = "Company N/A"
        if hasattr(res, "job_id") and res.job_id:
            comp_name = getattr(res.explanation_result, "company_name", None) or "ABC Technologies"

        lines.append(divider)
        lines.append("")
        lines.append(f"{res.title_result.job_title or 'Job'}")
        lines.append("")
        lines.append("Company:")
        lines.append(f"{res.explanation_result.summary.split('at ')[-1] if 'at ' in res.explanation_result.summary else 'Company'}")
        lines.append("")
        lines.append("Overall Match:")
        lines.append(f"{score_percent}%")
        lines.append("")
        lines.append("Recommendation:")
        lines.append(f"{res.recommendation_level}")
        lines.append("")
        lines.append("Summary:")
        lines.append(f"{res.explanation_result.summary}")
        lines.append("")

        if res.explanation_result.strengths:
            lines.append("Strengths")
            lines.append("")
            for st in res.explanation_result.strengths:
                lines.append(f"✓ {st}")
            lines.append("")

        if res.explanation_result.weaknesses:
            lines.append("Weaknesses")
            lines.append("")
            for wk in res.explanation_result.weaknesses:
                lines.append(f"• {wk}")
            lines.append("")

    lines.append(divider)
    return "\n".join(lines)
