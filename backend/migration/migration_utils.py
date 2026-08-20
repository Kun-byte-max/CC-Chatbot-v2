import os
import logging
import sqlite3
from typing import List, Dict, Any

# Configurations
DATABASE_URL = os.getenv("DATABASE_URL", "backend/collarcheck.db")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Logging setup
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("migration_pipeline")

def get_connection():
    """Return database connection object based on configured DATABASE_URL."""
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    return conn

def setup_canonical_tables():
    """Ensure designations and company master/alias tables exist in the target database."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Create designation_master
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS designation_master (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_name VARCHAR(255) NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create designation_alias
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS designation_alias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_id INTEGER NOT NULL,
            alias_name VARCHAR(255) NOT NULL UNIQUE,
            source_designation_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (canonical_id) REFERENCES designation_master(id)
        )
    """)
    
    # Create company_master
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS company_master (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_name VARCHAR(255) NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create company_alias
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS company_alias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_id INTEGER NOT NULL,
            alias_name VARCHAR(255) NOT NULL UNIQUE,
            source_company_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (canonical_id) REFERENCES company_master(id)
        )
    """)
    
    conn.commit()
    conn.close()
