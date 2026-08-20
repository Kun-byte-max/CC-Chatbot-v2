"""
inspect_profile_api.py — Inspect raw profile API payload structure and candidate_prof mapping.
"""

import sys
import os
import json
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.recommendation.mappers import to_candidate_profile_from_api
from backend.services import user_data_service

def inspect():
    print("=== INSPECTING PROFILE MAPPING ===")

    # Test sample API responses from real/mock CollarCheck user-profile endpoint
    sample_api_data_1 = {
        "status": True,
        "message": "User profile fetched",
        "data": {
            "id": 19,
            "fname": "Test",
            "lname": "User",
            "all_Skill": [
                {"id": 1, "skill": "Python", "rating": 5},
                {"id": 2, "skill": "FastAPI", "rating": 4},
                {"id": 3, "skill": "React", "rating": 4}
            ],
            "experience_years": 3,
            "city_name": "Bangalore"
        }
    }

    prof1 = to_candidate_profile_from_api(sample_api_data_1)
    print(f"Sample 1 mapped skills: {prof1.skills}")

    sample_api_data_2 = {
        "status": True,
        "data": {
            "id": 19,
            "skills": ["PHP", "Laravel", "MySQL"],
            "designation": "Backend Developer"
        }
    }

    prof2 = to_candidate_profile_from_api(sample_api_data_2)
    print(f"Sample 2 mapped skills: {prof2.skills}")

    sample_api_data_3 = {
        "status": True,
        "data": {
            "id": 19,
            "user_skills": [{"name": "Node.js"}, {"skill_name": "MongoDB"}]
        }
    }

    prof3 = to_candidate_profile_from_api(sample_api_data_3)
    print(f"Sample 3 mapped skills: {prof3.skills}")

if __name__ == "__main__":
    inspect()
