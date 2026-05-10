"""
PERIDOT KERNEL | EPHEMERAL RAM CACHE (Layer 1)
Module: core_system/memory/ephemeral_cache.py
# Engineered by uncoalesced
"""

import faiss
import numpy as np
import logging
from sentence_transformers import SentenceTransformer
from core_system.audit import ghost

logger = logging.getLogger("Peridot-Memory")

class EphemeralCache:
    def __init__(self, model_name='all-MiniLM-L6-v2', threshold=0.90):
        """
        Initializes the Layer 1 RAM Cache.
        :param threshold: Minimum Cosine Similarity score (0.0 to 1.0) to trigger a cache hit.
        """
        self.logger = logger
        self.threshold = threshold
        self.queries = []
        self.responses = []

        self.logger.info(f"Loading CPU Embedding Model: {model_name}...")
        
        # SECURITY & HARDWARE: We strictly bind the embedding model to the CPU.
        # This ensures the cache never consumes VRAM meant for the LLM or Medical Research.
        self.encoder = SentenceTransformer(model_name, device='cpu')
        
        # 'all-MiniLM-L6-v2' outputs 384-dimensional vectors
        self.embedding_dim = self.encoder.get_sentence_embedding_dimension()
        
        # Using Inner Product (IP) which equals Cosine Similarity when vectors are normalized
        self.index = faiss.IndexFlatIP(self.embedding_dim)
        self.logger.info("Layer 1 FAISS RAM Cache Initialized.")

    def _get_normalized_embedding(self, text: str) -> np.ndarray:
        """Converts text to a normalized 384D vector array."""
        emb = self.encoder.encode([text])[0]
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm
        return np.array([emb], dtype=np.float32)

    def add(self, query: str, response: str):
        """Embeds the query and stores the response in RAM."""
        emb = self._get_normalized_embedding(query)
        self.index.add(emb)
        self.queries.append(query)
        self.responses.append(response)
        ghost.info(f"CACHE_WRITE | L1_Ephemeral | Query: {query}")

    def search(self, query: str) -> str | None:
        """
        Searches the FAISS index for a highly similar previous query.
        Returns the cached response if similarity > threshold, else None.
        """
        if self.index.ntotal == 0:
            return None

        emb = self._get_normalized_embedding(query)
        
        # Search for the single nearest neighbor (k=1)
        similarities, indices = self.index.search(emb, 1)
        
        best_score = float(similarities[0][0])
        best_idx = int(indices[0][0])

        if best_score >= self.threshold:
            self.logger.info(f"CACHE HIT (Score: {best_score:.3f}) - Bypassing LLM.")
            ghost.info(f"CACHE_HIT | L1_Ephemeral | Score: {best_score} | Query: {query}")
            return self.responses[best_idx]

        # FIX: Converted from ghost.record to standard ghost.info string formatting
        ghost.info(f"CACHE_MISS | L1_Ephemeral | Score: {best_score} | Query: {query}")
        return None