try:
    from backend.services.normalization_service import (
        normalize_job_title,
        normalize_company_name,
        normalize_skill,
        normalize_location
    )
except ModuleNotFoundError:
    from services.normalization_service import (
        normalize_job_title,
        normalize_company_name,
        normalize_skill,
        normalize_location
    )

class SemanticService:
    @staticmethod
    def get_canonical_job_title(title: str) -> str:
        return normalize_job_title(title)

    @staticmethod
    def get_canonical_company_name(company: str) -> str:
        return normalize_company_name(company)

    @staticmethod
    def get_canonical_skill(skill: str) -> str:
        return normalize_skill(skill)

    @staticmethod
    def get_canonical_location(location: str) -> str:
        return normalize_location(location)
