# CC-Chatbot Normalization & Data Migration Pipeline

This folder contains a production-grade, idempotent data migration pipeline that extracts existing designations and company names, cleans/normalizes them, generates canonical entities, and maps them in alias tables.

## 1. File Structure
- `migrate_designations.py`: Main ETL script for designations.
- `migrate_companies.py`: Main ETL script for company names.
- `normalization.py`: Modular text normalization rules (regex cleanups, abbreviations expansion, suffix removals).
- `migration_utils.py`: General logging configurations, database setup, connection management, and batch operations.
- `validation.py`: Verification logic, manual review queue criteria, and summary stats exporter.
- `reports/`: Folder containing output verification files and CSV review queues.

---

## 2. Architecture & Design Principles

### Non-Destructive / Safety First
Original columns and database rows are never modified or removed. Instead, canonical entries and alias mappings are created.

### Idempotency
The scripts check for existing aliases and canonical names before inserting new records. The scripts can be run multiple times safely.

### Batch Processing & Memory Efficiency
Data is fetched and written in batches (controlled by `BATCH_SIZE` env var) rather than loading the entire table into memory, making it highly scalable for millions of rows.

### Fault Tolerance & Transactions
Each batch runs inside a dedicated database transaction block. If an error occurs, that specific batch is rolled back and logged, but the overall pipeline execution continues uninterrupted.

---

## 3. Running the Pipeline

### Setup environment variables (Optional)
```powershell
$env:DATABASE_URL = "backend/collarcheck.db"
$env:BATCH_SIZE = "100"
$env:LOG_LEVEL = "INFO"
```

### Dry Run (Simulates the run without database writes)
```bash
python backend/migration/migrate_designations.py --dry-run
python backend/migration/migrate_companies.py --dry-run
```

### Execution (Applies the normalized canonical records and alias mappings)
```bash
python backend/migration/migrate_designations.py
python backend/migration/migrate_companies.py
```

---

## 4. Reports & Manual Review Queue

All outputs are saved to the `reports/` directory:
- `review_designation.csv`: Flagged designations requiring manual review (e.g. role keywords like "Architect" or "Consultant" that should not be merged with generic roles).
- `review_company.csv`: Flagged company names requiring manual validation (e.g. names too short or containing digits).
- `summary_report.txt`: Processed metrics, unique canonical entries, duplicates, and conflicts.
