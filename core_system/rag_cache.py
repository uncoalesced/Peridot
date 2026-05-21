# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | AETHER-ROUTE LRU CACHE
# Copyright (C) 2026 uncoalesced
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import sqlite3
import json
import time
import os
from collections import OrderedDict
from typing import List, Optional
from config import STORAGE_PATH

class AetherCache:
    def __init__(self, max_ram_items=50):
        self.db_path = STORAGE_PATH / "aether_cold_storage.db"
        self.max_ram_items = max_ram_items
        self.ram_cache = OrderedDict() 
        self._init_db()
        print(f"[AETHER-ROUTE] Tiered LRU Cache Online. RAM Limit: {self.max_ram_items} chunks.")

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS vector_storage (
                    chunk_id TEXT PRIMARY KEY,
                    vector_data TEXT,
                    last_accessed REAL
                )
            ''')

    def put(self, chunk_id: str, vector: List[float]):
        if chunk_id in self.ram_cache:
            self.ram_cache.move_to_end(chunk_id)
        
        self.ram_cache[chunk_id] = vector
        if len(self.ram_cache) > self.max_ram_items:
            self._evict_oldest()

    def get(self, chunk_id: str) -> Optional[List[float]]:
        if chunk_id in self.ram_cache:
            self.ram_cache.move_to_end(chunk_id)
            return self.ram_cache[chunk_id]
            
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT vector_data FROM vector_storage WHERE chunk_id = ?', (chunk_id,))
            row = cursor.fetchone()
            if row:
                vector = json.loads(row[0])
                self.put(chunk_id, vector) 
                return vector
        return None

    def _evict_oldest(self):
        oldest_id, oldest_vector = self.ram_cache.popitem(last=False)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'INSERT OR REPLACE INTO vector_storage (chunk_id, vector_data, last_accessed) VALUES (?, ?, ?)',
                (oldest_id, json.dumps(oldest_vector), time.time())
            )