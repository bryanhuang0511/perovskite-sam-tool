"""Database Persistent Module for Perovskite SAM Extractor.

Implements Dual-Track Storage:
1. SQLite Database (data/sam_database.db) with indexable tables for jobs and 35-column records.
2. CSV Backup File (data/sam_database.csv) for direct spreadsheet access.
"""
import os
import json
import sqlite3
import datetime
from typing import List, Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "sam_database.db")
CSV_PATH = os.path.join(DATA_DIR, "sam_database.csv")

COLUMN_KEYS = [
    "ref_id", "sam_material", "smiles", "nio2",
    "ethanol", "toluene", "ipa", "thf", "chlorobenzene", "methoxyethanol_2", "ch2cl2",
    "concentration", "wash", "energy_e",
    "cs", "fa", "ma", "pb", "sn", "i", "br", "cl",
    "c60", "bcp", "pc60bm", "pcbm", "pc61bm", "peai", "ald_sno2",
    "pce", "reference_doi", "ref_author", "ref_journal", "notes"
]


def get_db_connection() -> sqlite3.Connection:
    """Ensure data directory exists and return SQLite connection."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize SQLite database tables if not exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Table 1: extraction_jobs (Tracks each execution job by ID, date, and filename)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS extraction_jobs (
        job_id TEXT PRIMARY KEY,
        filename TEXT NOT NULL,
        created_at TEXT NOT NULL,
        date_str TEXT NOT NULL,
        sam_count INTEGER DEFAULT 0,
        doi_count INTEGER DEFAULT 0,
        status TEXT DEFAULT 'completed'
    );
    """)

    # Table 2: sam_records (Stores 35-column SAM dataset per row linked to job_id)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sam_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        filename TEXT NOT NULL,
        ref_id TEXT,
        sam_material TEXT,
        smiles TEXT,
        nio2 INTEGER DEFAULT 0,
        ethanol INTEGER DEFAULT 0,
        toluene INTEGER DEFAULT 0,
        ipa INTEGER DEFAULT 0,
        thf INTEGER DEFAULT 0,
        chlorobenzene INTEGER DEFAULT 0,
        methoxyethanol_2 INTEGER DEFAULT 0,
        ch2cl2 INTEGER DEFAULT 0,
        concentration REAL,
        wash INTEGER DEFAULT 0,
        energy_e REAL,
        cs REAL DEFAULT 0,
        fa REAL DEFAULT 0,
        ma REAL DEFAULT 0,
        pb REAL DEFAULT 0,
        sn REAL DEFAULT 0,
        i REAL DEFAULT 0,
        br REAL DEFAULT 0,
        cl REAL DEFAULT 0,
        c60 INTEGER DEFAULT 0,
        bcp INTEGER DEFAULT 0,
        pc60bm INTEGER DEFAULT 0,
        pcbm INTEGER DEFAULT 0,
        pc61bm INTEGER DEFAULT 0,
        peai INTEGER DEFAULT 0,
        ald_sno2 INTEGER DEFAULT 0,
        pce REAL,
        reference_doi TEXT,
        ref_author TEXT,
        ref_journal TEXT,
        confidence_colors TEXT,
        notes TEXT,
        FOREIGN KEY (job_id) REFERENCES extraction_jobs (job_id)
    );
    """)

    conn.commit()
    conn.close()


def generate_job_id() -> str:
    """Generate a unique job ID with date prefix (e.g. JOB_20260804_083630_A1B2)."""
    now = datetime.datetime.now()
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")
    import random
    suffix = f"{random.randint(1000, 9999):04X}"
    return f"JOB_{timestamp_str}_{suffix}"


def save_job_and_records(
    filename: str,
    sam_dataset: List[Dict[str, Any]],
    doi_list: List[Dict[str, Any]] = None,
    job_id: Optional[str] = None
) -> str:
    """Save extraction job to both SQLite database and CSV file."""
    init_db()
    
    if not job_id:
        job_id = generate_job_id()

    now = datetime.datetime.now()
    created_at = now.strftime("%Y-%m-%d %H:%M:%S")
    date_str = now.strftime("%Y-%m-%d")

    doi_count = len(doi_list) if doi_list else 0
    sam_count = len(sam_dataset) if sam_dataset else 0

    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Insert into extraction_jobs table
    cursor.execute("""
    INSERT OR REPLACE INTO extraction_jobs (job_id, filename, created_at, date_str, sam_count, doi_count, status)
    VALUES (?, ?, ?, ?, ?, ?, 'completed');
    """, (job_id, filename, created_at, date_str, sam_count, doi_count))

    # 2. Insert into sam_records table
    for row in sam_dataset:
        colors_json = json.dumps(row.get("confidence_colors", {}))
        cursor.execute("""
        INSERT INTO sam_records (
            job_id, created_at, filename, ref_id, sam_material, smiles, nio2,
            ethanol, toluene, ipa, thf, chlorobenzene, methoxyethanol_2, ch2cl2,
            concentration, wash, energy_e, cs, fa, ma, pb, sn, i, br, cl,
            c60, bcp, pc60bm, pcbm, pc61bm, peai, ald_sno2, pce, reference_doi,
            ref_author, ref_journal, confidence_colors, notes
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        );
        """, (
            job_id, created_at, filename,
            row.get("ref_id", ""),
            row.get("sam_material", ""),
            row.get("smiles", ""),
            int(row.get("nio2", 0) or 0),
            int(row.get("ethanol", 0) or 0),
            int(row.get("toluene", 0) or 0),
            int(row.get("ipa", 0) or 0),
            int(row.get("thf", 0) or 0),
            int(row.get("chlorobenzene", 0) or 0),
            int(row.get("methoxyethanol_2", 0) or 0),
            int(row.get("ch2cl2", 0) or 0),
            float(row.get("concentration", 0) or 0) if row.get("concentration") is not None else None,
            int(row.get("wash", 0) or 0),
            float(row.get("energy_e", 0) or 0) if row.get("energy_e") is not None else None,
            float(row.get("cs", 0) or 0),
            float(row.get("fa", 0) or 0),
            float(row.get("ma", 0) or 0),
            float(row.get("pb", 0) or 0),
            float(row.get("sn", 0) or 0),
            float(row.get("i", 0) or 0),
            float(row.get("br", 0) or 0),
            float(row.get("cl", 0) or 0),
            int(row.get("c60", 0) or 0),
            int(row.get("bcp", 0) or 0),
            int(row.get("pc60bm", 0) or 0),
            int(row.get("pcbm", 0) or 0),
            int(row.get("pc61bm", 0) or 0),
            int(row.get("peai", 0) or 0),
            int(row.get("ald_sno2", 0) or 0),
            float(row.get("pce", 0) or 0) if row.get("pce") is not None else None,
            row.get("reference_doi", ""),
            row.get("ref_author", ""),
            row.get("ref_journal", ""),
            colors_json,
            row.get("notes", "")
        ))

    conn.commit()
    conn.close()

    # 3. Append to CSV backup file
    _append_to_csv_backup(job_id, created_at, filename, sam_dataset)

    return job_id


def _append_to_csv_backup(job_id: str, created_at: str, filename: str, sam_dataset: List[Dict[str, Any]]):
    """Append records to CSV backup file data/sam_database.csv."""
    import csv
    file_exists = os.path.exists(CSV_PATH)
    
    fieldnames = ["job_id", "created_at", "filename"] + COLUMN_KEYS
    
    with open(CSV_PATH, mode="a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        
        for row in sam_dataset:
            csv_row = {
                "job_id": job_id,
                "created_at": created_at,
                "filename": filename,
            }
            for col in COLUMN_KEYS:
                csv_row[col] = row.get(col, "")
            writer.writerow(csv_row)


def get_all_jobs(date_str: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve all extraction jobs, optionally filtered by date string (e.g. 2026-08-04)."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    if date_str and date_str.strip():
        cursor.execute("SELECT * FROM extraction_jobs WHERE date_str = ? ORDER BY created_at DESC", (date_str.strip(),))
    else:
        cursor.execute("SELECT * FROM extraction_jobs ORDER BY created_at DESC")

    rows = cursor.fetchall()
    jobs = [dict(r) for r in rows]
    conn.close()
    return jobs


def get_job_detail(job_id: str) -> Dict[str, Any]:
    """Retrieve job details and its 35-column SAM records."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM extraction_jobs WHERE job_id = ?", (job_id,))
    job_row = cursor.fetchone()
    if not job_row:
        conn.close()
        return {}

    job = dict(job_row)

    cursor.execute("SELECT * FROM sam_records WHERE job_id = ? ORDER BY id ASC", (job_id,))
    records_rows = cursor.fetchall()
    
    records = []
    for r in records_rows:
        rec = dict(r)
        if rec.get("confidence_colors"):
            try:
                rec["confidence_colors"] = json.loads(rec["confidence_colors"])
            except Exception:
                rec["confidence_colors"] = {}
        records.append(rec)

    job["sam_dataset"] = records
    conn.close()
    return job


def search_records(query: str) -> List[Dict[str, Any]]:
    """Search records across all jobs by SAM material name, SMILES, DOI, or filename."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    like_q = f"%{query.strip()}%"
    cursor.execute("""
    SELECT * FROM sam_records
    WHERE sam_material LIKE ? OR smiles LIKE ? OR reference_doi LIKE ? OR filename LIKE ? OR notes LIKE ?
    ORDER BY created_at DESC LIMIT 200;
    """, (like_q, like_q, like_q, like_q, like_q))

    rows = cursor.fetchall()
    results = []
    for r in rows:
        rec = dict(r)
        if rec.get("confidence_colors"):
            try:
                rec["confidence_colors"] = json.loads(rec["confidence_colors"])
            except Exception:
                rec["confidence_colors"] = {}
        results.append(rec)

    conn.close()
    return results
