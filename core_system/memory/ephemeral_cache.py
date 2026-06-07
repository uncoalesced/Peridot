# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | L1 EPHEMERAL CACHE
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import faiss
import numpy as np
import logging
from core_system.audit import ghost
from core_system.memory.embedder import embedder

logger = logging.getLogger("Peridot-Memory")

class EphemeralCache:
    def __init__(self, threshold=0.90):
        self.logger = logger
        self.threshold = threshold
        self.queries = []
        self.responses = []

        self.embedding_dim = 384
        self.index = faiss.IndexFlatIP(self.embedding_dim)
        self.logger.info("Layer 1 FAISS RAM Cache Initialised.")

    def _get_normalized_embedding(self, text: str) -> np.ndarray:
        emb = embedder.embed_query(text)[0]
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm
        return np.array([emb], dtype=np.float32)

    def add(self, query: str, response: str):
        emb = self._get_normalized_embedding(query)
        self.index.add(emb)
        self.queries.append(query)
        self.responses.append(response)
        ghost.info(f"CACHE_WRITE | L1_Ephemeral | Query: {query}")

    def search(self, query: str) -> str | None:
        if self.index.ntotal == 0:
            return None

        emb = self._get_normalized_embedding(query)
        similarities, indices = self.index.search(emb, 1)
        
        best_score = float(similarities[0][0])
        best_idx = int(indices[0][0])

        if best_score >= self.threshold:
            self.logger.info(f"CACHE HIT (Score: {best_score:.3f}) - Bypassing LLM.")
            ghost.info(f"CACHE_HIT | L1_Ephemeral | Score: {best_score} | Query: {query}")
            return self.responses[best_idx]

        ghost.info(f"CACHE_MISS | L1_Ephemeral | Score: {best_score} | Query: {query}")
        return None