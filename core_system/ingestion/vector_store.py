"""
Module: Vector Store (Semantic Memory)
Manages localized FAISS indexing and embedding generation.
# Engineered by uncoalesced
"""

import os
import sys
import json
import numpy as np
from pathlib import Path

try:
    import faiss
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("[ERROR] Missing RAG dependencies. Run: pip install faiss-cpu sentence-transformers")
    sys.exit(1)

try:
    from core_system.enhancedlogger import logger
except ImportError:
    import logging
    logger = logging.getLogger("vector_store")

# -----------------------------------------------------------------------------
# STORAGE CONFIGURATION
# -----------------------------------------------------------------------------
STORAGE_DIR = Path(r"E:\Peridot\storage\vector_db")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

INDEX_FILE = STORAGE_DIR / "peridot_kernel.index"
METADATA_FILE = STORAGE_DIR / "metadata.json"

# Lightweight, high-performance local embedding model
MODEL_NAME = "all-MiniLM-L6-v2"

class PeridotVectorStore:
    def __init__(self):
        logger.info(f"Initializing Semantic Memory Engine ({MODEL_NAME})...", source="V_STORE")
        
        # MANDATE: Run embeddings on CPU to preserve Blackwell VRAM and ensure sm_120 compatibility.
        self.model = SentenceTransformer(MODEL_NAME, device='cpu')
        self.dimension = self.model.get_sentence_embedding_dimension()
        
        if INDEX_FILE.exists():
            try:
                self.index = faiss.read_index(str(INDEX_FILE))
                with open(METADATA_FILE, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
                logger.info("Existing vector index loaded from disk.", source="V_STORE")
            except Exception as e:
                logger.error(f"Failed to load existing index: {e}. Reinitializing...", source="V_STORE")
                self._initialize_new_index()
        else:
            self._initialize_new_index()

    def _initialize_new_index(self):
        self.index = faiss.IndexFlatL2(self.dimension)
        self.metadata = []
        logger.info("New vector index initialized.", source="V_STORE")

    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> list:
        """Recursive character splitting to maintain context integrity."""
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start += chunk_size - overlap
        return chunks

    def add_document(self, text: str, source_name: str):
        """Embeds and indexes document chunks using CPU resources."""
        if not text:
            return

        chunks = self.chunk_text(text)
        
        # Model is locked to CPU, no Blackwell mismatch possible here
        embeddings = self.model.encode(chunks, show_progress_bar=False)
        
        embeddings_np = np.array(embeddings).astype('float32')
        self.index.add(embeddings_np)
        
        for chunk in chunks:
            self.metadata.append({
                "source": source_name,
                "content": chunk
            })
            
        self._save()
        logger.info(f"Indexed {len(chunks)} chunks from {source_name}.", source="V_STORE")

    def search(self, query: str, top_k: int = 3) -> list:
        """Performs similarity search against local memory."""
        query_vector = self.model.encode([query], device='cpu').astype('float32')
        distances, indices = self.index.search(query_vector, top_k)
        
        results = []
        for idx in indices[0]:
            if idx != -1 and idx < len(self.metadata):
                results.append(self.metadata[idx])
        
        return results

    def _save(self):
        """Persists the index and metadata to the secure storage zone."""
        faiss.write_index(self.index, str(INDEX_FILE))
        with open(METADATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, indent=2)

# Singleton instance for the kernel
vector_store = PeridotVectorStore()