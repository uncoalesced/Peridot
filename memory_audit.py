# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | MEMORY AUDIT
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import sqlite3
import time

def audit_vault():
    conn = sqlite3.connect("storage/vector_db/aether_cold_storage.db")
    cursor = conn.execute("SELECT chunk_id, last_accessed FROM vector_storage")
    rows = cursor.fetchall()
    print(f"\n--- PERIDOT MEMORY AUDIT: {len(rows)} CHUNKS INDEXED ---")
    for row in rows:
        print(f"Chunk: {row[0]} | Last Accessed: {time.ctime(row[1])}")
    conn.close()

if __name__ == "__main__":
    audit_vault()