import os
import sys
import argparse

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from backend.migration.migration_utils import get_connection, setup_canonical_tables, BATCH_SIZE, logger
from backend.migration.normalization import normalize_company_name
from backend.migration.validation import ValidationReporter

def migrate_companies(dry_run: bool = False):
    setup_canonical_tables()
    
    reporter = ValidationReporter()
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get total count of companies
    cursor.execute("SELECT COUNT(*) FROM cyb_user WHERE user_type = 2")
    total_records = cursor.fetchone()[0]
    logger.info(f"Starting company migration. Total source records: {total_records} (Dry Run: {dry_run})")
    
    offset = 0
    processed_count = 0
    
    while True:
        cursor.execute("SELECT id, fname FROM cyb_user WHERE user_type = 2 LIMIT ? OFFSET ?", (BATCH_SIZE, offset))
        rows = cursor.fetchall()
        if not rows:
            break
            
        if not dry_run:
            conn.execute("BEGIN TRANSACTION")
            
        try:
            for row in rows:
                orig_id = row["id"]
                orig_name = row["fname"]
                
                if not orig_name:
                    continue
                    
                canonical_name = normalize_company_name(orig_name)
                reporter.stats["companies_processed"] += 1
                
                # Check for validation queueing
                is_for_review = reporter.check_company_for_review(orig_id, orig_name, canonical_name)
                
                if not dry_run:
                    # 1. Fetch or create canonical company master
                    cursor.execute("SELECT id FROM company_master WHERE canonical_name = ?", (canonical_name,))
                    master_row = cursor.fetchone()
                    if master_row:
                        canonical_id = master_row[0]
                    else:
                        cursor.execute("INSERT INTO company_master (canonical_name) VALUES (?)", (canonical_name,))
                        canonical_id = cursor.lastrowid
                        reporter.stats["unique_canonical_companies"] += 1
                        
                    # 2. Check and insert alias if not present
                    cursor.execute("SELECT id FROM company_alias WHERE alias_name = ?", (orig_name,))
                    if not cursor.fetchone():
                        cursor.execute(
                            "INSERT INTO company_alias (canonical_id, alias_name, source_company_id) VALUES (?, ?, ?)",
                            (canonical_id, orig_name, orig_id)
                        )
                        reporter.stats["company_aliases"] += 1
                else:
                    # Dry run count simulations
                    reporter.stats["unique_canonical_companies"] += 1
                    reporter.stats["company_aliases"] += 1
                    
            if not dry_run:
                conn.commit()
                logger.info(f"Processed batch. Committed offset {offset}.")
            else:
                logger.info(f"Dry-run: Processed batch offset {offset}.")
                
        except Exception as e:
            if not dry_run:
                conn.rollback()
            logger.error(f"Transaction failed at offset {offset}, changes rolled back. Error: {str(e)}")
            
        offset += BATCH_SIZE
        processed_count += len(rows)
        
    conn.close()
    reporter.export_reports(entity_type="company")
    logger.info("Company migration pipeline completed successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Companies Normalization ETL Migration Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Simulate ETL without writing to DB")
    args = parser.parse_args()
    
    migrate_companies(dry_run=args.dry_run)
