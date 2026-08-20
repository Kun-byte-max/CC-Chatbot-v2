import os
import sys
import argparse
import csv

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from backend.migration.migration_utils import get_connection, setup_canonical_tables, BATCH_SIZE, logger
from backend.migration.normalization import normalize_job_title
from backend.migration.validation import ValidationReporter

def import_csv_if_missing():
    """Import cyb_designation.csv into SQLite if the table is missing."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cyb_designation'")
    if not cursor.fetchone():
        logger.info("cyb_designation table is missing in SQLite. Creating and loading from CSV...")
        cursor.execute("""
            CREATE TABLE cyb_designation (
                id INTEGER PRIMARY KEY,
                name VARCHAR(255),
                status INTEGER,
                user_id INTEGER,
                user_defined INTEGER,
                slug VARCHAR(255),
                create_date VARCHAR(255),
                modify_date VARCHAR(255)
            )
        """)
        csv_path = "d:/UNG/CC-Chatbot-v2 - Copy/database/cyb_designation.csv"
        if os.path.exists(csv_path):
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                batch = []
                for row in reader:
                    batch.append((
                        row["id"], row["name"], row["status"], row["user_id"],
                        row["user_defined"], row["slug"], row["create_date"], row["modify_date"]
                    ))
                    if len(batch) >= 1000:
                        cursor.executemany("INSERT INTO cyb_designation VALUES (?,?,?,?,?,?,?,?)", batch)
                        batch = []
                if batch:
                    cursor.executemany("INSERT INTO cyb_designation VALUES (?,?,?,?,?,?,?,?)", batch)
            conn.commit()
            logger.info("Successfully loaded cyb_designation from CSV.")
        else:
            logger.warning(f"CSV file not found at {csv_path}. Cannot pre-populate designations.")
    conn.close()

def migrate_designations(dry_run: bool = False):
    setup_canonical_tables()
    import_csv_if_missing()
    
    reporter = ValidationReporter()
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get total count
    cursor.execute("SELECT COUNT(*) FROM cyb_designation")
    total_records = cursor.fetchone()[0]
    logger.info(f"Starting designation migration. Total source records: {total_records} (Dry Run: {dry_run})")
    
    offset = 0
    processed_count = 0
    
    while True:
        cursor.execute("SELECT id, name FROM cyb_designation LIMIT ? OFFSET ?", (BATCH_SIZE, offset))
        rows = cursor.fetchall()
        if not rows:
            break
            
        batch_inserts_master = []
        batch_inserts_alias = []
        
        # Start a transaction block for database writes
        if not dry_run:
            conn.execute("BEGIN TRANSACTION")
            
        try:
            for row in rows:
                orig_id = row["id"]
                orig_name = row["name"]
                
                if not orig_name:
                    continue
                    
                canonical_name = normalize_job_title(orig_name)
                reporter.stats["designations_processed"] += 1
                
                # Check for validation queueing
                is_for_review = reporter.check_designation_for_review(orig_id, orig_name, canonical_name)
                
                if not dry_run:
                    # 1. Fetch or create canonical designation master
                    cursor.execute("SELECT id FROM designation_master WHERE canonical_name = ?", (canonical_name,))
                    master_row = cursor.fetchone()
                    if master_row:
                        canonical_id = master_row[0]
                    else:
                        cursor.execute("INSERT INTO designation_master (canonical_name) VALUES (?)", (canonical_name,))
                        canonical_id = cursor.lastrowid
                        reporter.stats["unique_canonical_designations"] += 1
                        
                    # 2. Check and insert alias if not present
                    cursor.execute("SELECT id FROM designation_alias WHERE alias_name = ?", (orig_name,))
                    if not cursor.fetchone():
                        cursor.execute(
                            "INSERT INTO designation_alias (canonical_id, alias_name, source_designation_id) VALUES (?, ?, ?)",
                            (canonical_id, orig_name, orig_id)
                        )
                        reporter.stats["designation_aliases"] += 1
                else:
                    # Dry run count simulations
                    reporter.stats["unique_canonical_designations"] += 1
                    reporter.stats["designation_aliases"] += 1
                    
            if not dry_run:
                conn.commit()
                logger.info(f"Processed batch. Committed offset {offset}.")
            else:
                logger.info(f"Dry-run: Processed batch offset {offset}.")
                
        except Exception as e:
            if not dry_run:
                conn.rollback()
            logger.error(f"Transaction failed at offset {offset}, changes rolled back. Error: {str(e)}")
            # Skip this batch and continue
            
        offset += BATCH_SIZE
        processed_count += len(rows)
        
    conn.close()
    reporter.export_reports(entity_type="designation")
    logger.info("Designation migration pipeline completed successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Designations Normalization ETL Migration Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Simulate ETL without writing to DB")
    args = parser.parse_args()
    
    migrate_designations(dry_run=args.dry_run)
