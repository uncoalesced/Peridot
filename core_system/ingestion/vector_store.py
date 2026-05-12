"""
Module: Vector Store (Semantic Memory)
Upgraded v1.3.2: Implements hash-based deduplication and source tracking.
# Engineered by uncoalesced
"""

import os
import sys
import json
import hashlib
import numpy as np
from pathlib import Path

# Suppress HF Hub warnings to maintain Sovereign UI aesthetics
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

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

STORAGE_DIR = Path(r"E:\Peridot\storage\vector_db")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

INDEX_FILE = STORAGE_DIR / "peridot_kernel.index"
METADATA_FILE = STORAGE_DIR / "metadata.json"
REGISTRY_FILE = STORAGE_DIR / "registry.json"  # Tracks indexed file hashes

MODEL_NAME = "all-MiniLM-L6-v2"

class PeridotVectorStore:
    def __init__(self):
        logger.info(f"Initializing Semantic Memory Engine ({MODEL_NAME})...", source="V_STORE")
        self.model = SentenceTransformer(MODEL_NAME, device='cpu')
        self.dimension = self.model.get_sentence_embedding_dimension()
        
        # Load Registry (File Hashing)
        self.registry = {}
        if REGISTRY_FILE.exists():
            with open(REGISTRY_FILE, "r") as f:
                self.registry = json.load(f)

        if INDEX_FILE.exists():
            try:
                self.index = faiss.read_index(str(INDEX_FILE))
                with open(METADATA_FILE, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
                logger.info(f"Vector index loaded. {len(self.metadata)} chunks in memory.", source="V_STORE")
            except Exception as e:
                logger.error(f"Index corruption detected: {e}. Resetting.", source="V_STORE")
                self._initialize_new_index()
        else:
            self._initialize_new_index()

    def _initialize_new_index(self):
        self.index = faiss.IndexFlatL2(self.dimension)
        self.metadata = []

    def _calculate_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    def add_document(self, text: str, source_name: str):
        """Indexes text only if the hash is unique."""
        doc_hash = self._calculate_hash(text)
        
        if self.registry.get(source_name) == doc_hash:
            logger.info(f"Skip: {source_name} is already indexed and unchanged.", source="V_STORE")
            return

        chunks = self._chunk_text(text)
        embeddings = self.model.encode(chunks, show_progress_bar=False)
        self.index.add(np.array(embeddings).astype('float32'))
        
        for chunk in chunks:
            self.metadata.append({"source": source_name, "content": chunk})
            
        self.registry[source_name] = doc_hash
        self._save()
        logger.info(f"Success: Indexed {len(chunks)} chunks from {source_name}.", source="V_STORE")

    def _chunk_text(self, text: str, chunk_size: int = 600, overlap: int = 100) -> list:
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start += chunk_size - overlap
        return chunks

    def search(self, query: str, top_k: int = 3) -> list:
        query_vector = self.model.encode([query], device='cpu').astype('float32')
        distances, indices = self.index.search(query_vector, top_k)
        return [self.metadata[idx] for idx in indices[0] if idx != -1 and idx < len(self.metadata)]

    def _save(self):
        faiss.write_index(self.index, str(INDEX_FILE))
        with open(METADATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, indent=2)
        with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
            json.dump(self.registry, f, indent=2)

vector_store = PeridotVectorStore()