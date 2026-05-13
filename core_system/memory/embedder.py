# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL
# Copyright (C) 2026 uncoalesced
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
Embedding Engine
Converts raw text into 384-dimensional semantic vectors.
Strictly CPU-bound to prevent GPU memory fragmentation.
"""

import sys
import time
from pathlib import Path
from typing import List
import numpy as np

# Suppress verbose huggingface/transformers logging
import os
import warnings
import logging
os.environ["TOKENIZERS_PARALLELISM"] = "false"
warnings.filterwarnings("ignore")
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)

from sentence_transformers import SentenceTransformer

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core_system.audit import ghost

class EmbeddingEngine:
    """Singleton CPU-bound embedding generator."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingEngine, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        start_time = time.time()
        ghost.info("EMBEDDER | Initializing isolated CPU embedding matrix...")
        
        # Hardcode to CPU. Do not allow PyTorch to autodetect the GPU.
        self.model = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
        
        elapsed = (time.time() - start_time) * 1000
        ghost.info(f"EMBEDDER | all-MiniLM-L6-v2 loaded in {elapsed:.2f}ms.")

    def embed_query(self, text: str) -> np.ndarray:
        """
        Embed a single user prompt.
        Returns a 2D float32 numpy array for FAISS ingestion.
        """
        start_time = time.time()
        
        # FAISS strictly requires float32 arrays
        vector = self.model.encode(text, convert_to_numpy=True, show_progress_bar=False)
        vector_2d = np.array(vector, dtype=np.float32).reshape(1, -1)
        
        elapsed = (time.time() - start_time) * 1000
        ghost.info(f"EMBEDDER | Query vectorized in {elapsed:.2f}ms.")
        
        return vector_2d

    def embed_documents(self, texts: List[str]) -> np.ndarray:
        """
        Batch embed document chunks for the Layer 2 Persistent Vault.
        """
        start_time = time.time()
        
        vectors = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        vectors_2d = np.array(vectors, dtype=np.float32)
        
        elapsed = (time.time() - start_time) * 1000
        ghost.info(f"EMBEDDER | Batch vectorized {len(texts)} chunks in {elapsed:.2f}ms.")
        
        return vectors_2d

# Global instance for seamless imports
embedder = EmbeddingEngine()