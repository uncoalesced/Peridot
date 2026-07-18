# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | L1 EPHEMERAL CACHE (TURBOVEC)
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------
"""
Layer 1 Ephemeral RAM Cache using TurboVec

Replaces FAISS IndexFlatIP with TurboVec IdMapIndex for:
- Consistent vector storage backend across L1/L2
- Better memory efficiency with 4-bit quantization
- No pickle serialization

Note: L1 cache is VOLATILE - it is not persisted to disk.
"""

import numpy as np
from typing import Optional
from core_system.audit import ghost
from core_system.memory.embedder import embedder
from core_system.memory.turbovec_index import IdMapIndex

class EphemeralCache:
    """
    Volatile RAM cache for recent query-response pairs.

    Uses cosine similarity threshold (0.90) for cache hits.
    All data is lost on shutdown - this is intentional for privacy.
    """

    def __init__(self, threshold: float = 0.90, dim: int = 384, bit_width: int = 4):
        """
        Initialize the ephemeral cache.

        Args:
            threshold: Cosine similarity threshold for cache hits (0.90 = 90% similar)
            dim: Vector dimension (384 for all-MiniLM-L6-v2)
            bit_width: Quantization bits (4 for memory efficiency)
        """
        self.threshold = threshold
        self.queries = []
        self.responses = []

        # Use TurboVec IdMapIndex for L2 distance search
        # Note: We normalize embeddings to get cosine similarity via L2 distance
        self.index = IdMapIndex(dim=dim, bit_width=bit_width)
        ghost.info(f"CACHE | L1 Ephemeral Cache initialised (threshold={threshold}, dim={dim})")

    def _get_normalized_embedding(self, text: str) -> np.ndarray:
        """
        Get a normalized embedding vector for cosine similarity.

        Normalizing vectors allows L2 distance to approximate cosine similarity:
        ||a/|a| - b/|b||^2 = 2 - 2*cos(a,b)
        """
        emb = embedder.embed_query(text)[0]
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm
        return np.ascontiguousarray([emb], dtype=np.float32)

    def add(self, query: str, response: str) -> None:
        """
        Add a query-response pair to the cache.

        Args:
            query: The user's query text
            response: The AI's response text
        """
        emb = self._get_normalized_embedding(query)
        # Use query hash as stable ID for potential future deletion
        cache_id = f"cache_{len(self.queries)}"
        self.index.add_with_ids(emb, [cache_id])
        self.queries.append(query)
        self.responses.append(response)
        ghost.info(f"CACHE_WRITE | L1_Ephemeral | Query: {query[:64]}...")

    def search(self, query: str) -> Optional[str]:
        """
        Search for a cached response to the given query.

        Args:
            query: The query text to find

        Returns:
            Cached response if found with similarity >= threshold, else None
        """
        if self.index.size == 0:
            return None

        emb = self._get_normalized_embedding(query)
        distances, ids, scores = self.index.search(emb, k=1)

        if len(distances) == 0:
            return None

        # Convert L2 distance to similarity score
        # For normalized vectors: cosine_sim = 1 - (distance^2 / 2)
        best_distance = float(distances[0])
        best_score = 1.0 / (1.0 + best_distance)

        if best_score >= self.threshold:
            # Find the index of the matching response
            # The ID format is "cache_N" where N is the index
            cache_id = ids[0]
            try:
                idx = int(cache_id.replace("cache_", ""))
                ghost.info(f"CACHE_HIT | L1_Ephemeral | Score: {best_score:.3f} | Query: {query[:64]}...")
                return self.responses[idx]
            except (ValueError, IndexError):
                pass

        ghost.info(f"CACHE_MISS | L1_Ephemeral | Score: {best_score:.3f} | Query: {query[:64]}...")
        return None

    def clear(self) -> None:
        """Clear all cached entries."""
        self.queries.clear()
        self.responses.clear()
        self.index = IdMapIndex(dim=self.index.dim, bit_width=self.index.bit_width)
        ghost.info("CACHE | L1 cache cleared.")