import os
import csv
from typing import List, Dict, Any

class ValidationReporter:
    def __init__(self, output_dir: str = "backend/migration/reports"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.designation_reviews = []
        self.company_reviews = []
        
        self.stats = {
            "designations_processed": 0,
            "unique_canonical_designations": 0,
            "designation_aliases": 0,
            "companies_processed": 0,
            "unique_canonical_companies": 0,
            "company_aliases": 0,
            "manual_reviews_flagged_designations": 0,
            "manual_reviews_flagged_companies": 0
        }

    def check_designation_for_review(self, original_id: int, original: str, canonical: str) -> bool:
        """Determines if a title mapping requires manual verification."""
        orig_lower = original.lower()
        canon_lower = canonical.lower()
        
        # Rule: Do not auto-merge different roles (Architect, Consultant, Lead, Intern, Manager)
        keywords = ["consultant", "architect", "lead", "manager", "intern", "head", "director", "advisor"]
        for kw in keywords:
            if (kw in orig_lower) != (kw in canon_lower):
                self.designation_reviews.append({
                    "original_id": original_id,
                    "original_name": original,
                    "canonical_name": canonical,
                    "reason": f"Potential role mismatch on keyword: '{kw}'"
                })
                self.stats["manual_reviews_flagged_designations"] += 1
                return True
                
        if len(orig_lower.split()) != len(canon_lower.split()) and not any(k in orig_lower for k in ["engineer", "programmer", "coder"]):
            self.designation_reviews.append({
                "original_id": original_id,
                "original_name": original,
                "canonical_name": canonical,
                "reason": "Word count mismatch"
            })
            self.stats["manual_reviews_flagged_designations"] += 1
            return True
            
        return False

    def check_company_for_review(self, original_id: int, original: str, canonical: str) -> bool:
        """Determines if a company mapping requires manual review."""
        # Rule: Very short company names (potential acronyms/abbreviations)
        if len(canonical) <= 2:
            self.company_reviews.append({
                "original_id": original_id,
                "original_name": original,
                "canonical_name": canonical,
                "reason": "Name is too short (acronym risk)"
            })
            self.stats["manual_reviews_flagged_companies"] += 1
            return True
            
        # Rule: Contains digits or strange symbols
        if any(char.isdigit() for char in canonical):
            self.company_reviews.append({
                "original_id": original_id,
                "original_name": original,
                "canonical_name": canonical,
                "reason": "Contains numbers"
            })
            self.stats["manual_reviews_flagged_companies"] += 1
            return True
            
        return False

    def export_reports(self, entity_type: str = "all"):
        """Save the validation logs and stats to reports/ directory."""
        if entity_type in ["designation", "all"]:
            designation_csv = os.path.join(self.output_dir, "review_designation.csv")
            with open(designation_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["original_id", "original_name", "canonical_name", "reason"])
                writer.writeheader()
                writer.writerows(self.designation_reviews)
                
            summary_txt = os.path.join(self.output_dir, "summary_designations.txt")
            with open(summary_txt, "w", encoding="utf-8") as f:
                f.write("=== DESIGNATION MIGRATION REPORT ===\n\n")
                for k in ["designations_processed", "unique_canonical_designations", "designation_aliases", "manual_reviews_flagged_designations"]:
                    f.write(f"{k.replace('_', ' ').title()}: {self.stats[k]}\n")
            
        if entity_type in ["company", "all"]:
            company_csv = os.path.join(self.output_dir, "review_company.csv")
            with open(company_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["original_id", "original_name", "canonical_name", "reason"])
                writer.writeheader()
                writer.writerows(self.company_reviews)
                
            summary_txt = os.path.join(self.output_dir, "summary_companies.txt")
            with open(summary_txt, "w", encoding="utf-8") as f:
                f.write("=== COMPANY MIGRATION REPORT ===\n\n")
                for k in ["companies_processed", "unique_canonical_companies", "company_aliases", "manual_reviews_flagged_companies"]:
                    f.write(f"{k.replace('_', ' ').title()}: {self.stats[k]}\n")
