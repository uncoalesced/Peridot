# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL v1.5.1 | RAG INTEGRITY DIAGNOSTIC TOOL
# Copyright (C) 2026 uncoalesced
# 
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import os
import sqlite3
from pathlib import Path

def audit_cold_storage():
    db_path = Path("storage/aether_cold_storage.db")
    print("==================================================")
    print("      PERIDOT SEMANTIC STORAGE AUDIT PROTOCOL     ")
    print("==================================================")
    
    if not db_path.exists():
        print(f"[CRITICAL FAILURE] Database binary not found at: {db_path}")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM vector_storage;")
        record_count = cursor.fetchall()[0][0]
        print(f"[DATA LOG] Total vectorized text chunks stored: {record_count}")
        
        if record_count > 0:
            cursor.execute("PRAGMA table_info(vector_storage);")
            columns = [col[1] for col in cursor.fetchall()]
            print(f"[SCHEMA] Mapped Columns: {columns}\n")
            
            print("[SAMPLE NODE LOOKUP]:")
            cursor.execute("SELECT * FROM vector_storage LIMIT 2;")
            samples = cursor.fetchall()
            
            for i, sample in enumerate(samples):
                print(f" ├── [Node {i}]")
                for col_name, val in zip(columns, sample):
                    # Truncate long text strings for terminal readability
                    val_str = str(val)[:120].replace('\n', ' ') + "..." if len(str(val)) > 120 else str(val).replace('\n', ' ')
                    print(f" │    └── {col_name}: {val_str}")
                print(" │")
                
        conn.close()
    except Exception as e:
        print(f"[ERROR] Failed to map vector_storage: {str(e)}")

if __name__ == "__main__":
    audit_cold_storage()