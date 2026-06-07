# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | CENTRAL EMBEDDER
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import sys
import time
import os
import warnings
import logging
import numpy as np

os.environ["TOKENIZERS_PARALLELISM"] = "false"
warnings.filterwarnings("ignore")
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)

from sentence_transformers import SentenceTransformer
from core_system.audit import ghost

class EmbeddingEngine:
    """Singleton CPU-bound embedding generator."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingEngine, cls).__new__(cls)
            cls._instance._initialise()
        return cls._instance

    def _initialise(self):
        start_time = time.time()
        ghost.info("EMBEDDER | Initialising isolated CPU embedding matrix...")
        
        # Hardcode to CPU. Do not allow PyTorch to autodetect the GPU.
        self.model = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
        
        elapsed = (time.time() - start_time) * 1000
        ghost.info(f"EMBEDDER | all-MiniLM-L6-v2 loaded in {elapsed:.2f}ms.")

    def embed_query(self, text: str) -> np.ndarray:
        """Embeds a single user prompt. Returns a 2D float32 numpy array."""
        start_time = time.time()
        vector = self.model.encode(text, convert_to_numpy=True, show_progress_bar=False)
        vector_2d = np.array(vector, dtype=np.float32).reshape(1, -1)
        elapsed = (time.time() - start_time) * 1000
        ghost.info(f"EMBEDDER | Query vectorised in {elapsed:.2f}ms.")
        return vector_2d

    def embed_documents(self, texts: list) -> np.ndarray:
        """Batch embed document chunks for the Layer 2 Persistent Vault."""
        start_time = time.time()
        vectors = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        vectors_2d = np.array(vectors, dtype=np.float32)
        elapsed = (time.time() - start_time) * 1000
        ghost.info(f"EMBEDDER | Batch vectorised {len(texts)} chunks in {elapsed:.2f}ms.")
        return vectors_2d

# Global instance for seamless imports
embedder = EmbeddingEngine()