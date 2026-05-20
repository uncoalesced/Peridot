# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL v1.5 (AETHER-ROUTE LRU CACHE)
# Copyright (C) 2026 uncoalesced
#
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import sqlite3
import json
import time
import os
from collections import OrderedDict
from typing import List, Optional

class AetherCache:
    def __init__(self, db_path="aether_cold_storage.db", max_ram_items=3):
        """
        Initializes the Tiered RAG Cache.
        max_ram_items is kept artificially low (3) for this simulation.
        In production, this would be based on actual MB usage (e.g., 4000MB).
        """
        self.db_path = db_path
        self.max_ram_items = max_ram_items
        
        # OrderedDict is the secret weapon for an LRU cache. 
        # It remembers the order items were inserted or accessed.
        self.ram_cache = OrderedDict() 
        self._init_db()
        print(f"[AETHER-ROUTE] Tiered LRU Cache Online. RAM Limit: {self.max_ram_items} chunks.")

    def _init_db(self):
        """Bootstraps the Tier 2 SQLite NVMe Database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS vector_storage (
                    chunk_id TEXT PRIMARY KEY,
                    vector_data TEXT,
                    last_accessed REAL
                )
            ''')

    def put(self, chunk_id: str, vector: List[float]):
        """Injects a new document vector into RAM, evicting old ones if necessary."""
        if chunk_id in self.ram_cache:
            # If it already exists, move it to the 'most recently used' end
            self.ram_cache.move_to_end(chunk_id)
        
        self.ram_cache[chunk_id] = vector
        print(f"[CACHE] Loaded '{chunk_id}' into Tier 1 (RAM).")
        
        if len(self.ram_cache) > self.max_ram_items:
            self._evict_oldest()

    def get(self, chunk_id: str) -> Optional[List[float]]:
        """Retrieves a vector. Checks RAM first, then falls back to SSD."""
        # 1. Check Tier 1 (RAM)
        if chunk_id in self.ram_cache:
            self.ram_cache.move_to_end(chunk_id)
            print(f"[CACHE HIT] '{chunk_id}' retrieved instantly from RAM.")
            return self.ram_cache[chunk_id]
            
        # 2. Check Tier 2 (SSD)
        print(f"[CACHE MISS] '{chunk_id}' not in RAM. Querying NVMe SSD...")
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT vector_data FROM vector_storage WHERE chunk_id = ?', (chunk_id,))
            row = cursor.fetchone()
            
            if row:
                vector = json.loads(row[0])
                # Promote it back to RAM
                self.put(chunk_id, vector) 
                print(f"[CACHE RESTORE] '{chunk_id}' promoted from SSD back to RAM.")
                return vector
                
        print(f"[CACHE FAULT] '{chunk_id}' does not exist in any tier.")
        return None

    def _evict_oldest(self):
        """The heart of the LRU. Banishes the coldest vector to the NVMe SSD."""
        # popitem(last=False) removes the FIRST item added (the oldest)
        oldest_id, oldest_vector = self.ram_cache.popitem(last=False)
        
        print(f"[MEMORY WATCHDOG] RAM saturation threshold met. Evicting '{oldest_id}' to SSD...")
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'INSERT OR REPLACE INTO vector_storage (chunk_id, vector_data, last_accessed) VALUES (?, ?, ?)',
                (oldest_id, json.dumps(oldest_vector), time.time())
            )

# --- TESTING THE AETHER-ROUTE CACHE ---
if __name__ == "__main__":
    # Clean up old test DB if it exists
    if os.path.exists("aether_cold_storage.db"):
        os.remove("aether_cold_storage.db")

    cache = AetherCache(max_ram_items=3)
    
    print("\n--- SIMULATING RAG DOCUMENT INGESTION ---")
    # We ingest 4 documents. Because the limit is 3, "Doc_A" will be violently evicted to the SSD.
    cache.put("Doc_A_Page_1", [0.11, 0.22, 0.33])
    cache.put("Doc_B_Page_1", [0.44, 0.55, 0.66])
    cache.put("Doc_C_Page_1", [0.77, 0.88, 0.99])
    cache.put("Doc_D_Page_1", [0.12, 0.34, 0.56]) # This triggers the eviction of Doc_A
    
    print("\n--- SIMULATING RAG RETRIEVAL ---")
    # This will be instant (it's in RAM)
    cache.get("Doc_C_Page_1") 
    
    # This will cause an SSD query and promote it back to RAM (evicting Doc_B)
    cache.get("Doc_A_Page_1")