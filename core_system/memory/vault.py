# -----------------------------------------------------------------------------
# PERIDOT VAULT | Layer 2 Retrieval-Augmented Generation
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import os
import faiss
import pickle
import numpy as np
import fitz  # PyMuPDF
import shutil
import gc
from pathlib import Path
from sentence_transformers import SentenceTransformer
from core_system.enhancedlogger import logger
from config import INPUT_PATH, PROCESSED_PATH

class PeridotVault:
    def __init__(self, model_name="all-MiniLM-L6-v2"):
        self.vault_path = PROCESSED_PATH
        self.index_file = self.vault_path / "peridot_vault.index"
        self.meta_file = self.vault_path / "peridot_vault.meta"
        
        logger.info(f"Loading Vault Embedding Engine ({model_name}) on CPU...", source="VAULT")
        
        # Hard-locked to CPU to prevent Blackwell sm_120 architecture collisions
        self.embedder = SentenceTransformer(model_name, device="cpu")
        self.dimension = self.embedder.get_sentence_embedding_dimension()
        
        self.index = None
        self.metadata = []  # Stores the actual text chunks
        self._load_vault()

    def _load_vault(self):
        """Loads the persistent FAISS index from disk."""
        if self.index_file.exists() and self.meta_file.exists():
            self.index = faiss.read_index(str(self.index_file))
            with open(self.meta_file, 'rb') as f:
                self.metadata = pickle.load(f)
            logger.info(f"Layer 2 Vault Online. {self.index.ntotal} sectors secured.", source="VAULT")
        else:
            self.index = faiss.IndexFlatL2(self.dimension)
            logger.info("Layer 2 Vault Initialized (Empty).", source="VAULT")

    def save_vault(self):
        """Commits the RAM index to disk."""
        faiss.write_index(self.index, str(self.index_file))
        with open(self.meta_file, 'wb') as f:
            pickle.dump(self.metadata, f)
        logger.info("Vault state committed to disk.", source="VAULT")

    def chunk_text(self, text, chunk_size=400, overlap=50):
        """Slices documents into overlapping context windows."""
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size - overlap):
            chunk = " ".join(words[i:i + chunk_size])
            if chunk:
                chunks.append(chunk)
        return chunks

    def ingest_directory(self):
        """Scans the input folder and ingests all unmapped PDFs."""
        pdf_files = list(INPUT_PATH.glob("*.pdf"))
        if not pdf_files:
            return

        logger.info(f"Scanning {len(pdf_files)} documents for ingestion...", source="VAULT")
        new_chunks = 0

        for pdf_path in pdf_files:
            try:
                full_text = ""
                # Strict context manager guarantees the file is released at the OS level
                with fitz.open(pdf_path) as doc:
                    for page in doc:
                        full_text += page.get_text("text") + "\n"
                
                chunks = self.chunk_text(full_text)
                if not chunks:
                    continue
                
                # Use the Ryzen CPU to vectorize the text
                embeddings = self.embedder.encode(chunks, convert_to_numpy=True)
                
                self.index.add(embeddings)
                self.metadata.extend(chunks)
                new_chunks += len(chunks)
                
                # Force Python to destroy any lingering C-pointers to the file
                gc.collect()
                
                # Robust Windows file move
                shutil.move(str(pdf_path), str(PROCESSED_PATH / pdf_path.name))
                logger.info(f"Ingested: {pdf_path.name}", source="VAULT")

            except Exception as e:
                logger.error(f"Vault ingestion failed for {pdf_path.name}: {e}", source="VAULT")

        if new_chunks > 0:
            self.save_vault()

    def search(self, query, top_k=3):
        """Retrieves the most relevant facts from the Vault."""
        if self.index is None or self.index.ntotal == 0:
            return None
            
        q_emb = self.embedder.encode([query], convert_to_numpy=True)
        distances, indices = self.index.search(q_emb, top_k)
        
        # RELAXED DISTANCE THRESHOLD: Allows shorter queries to match longer text blocks
        if distances[0][0] > 1.85:  
            return None

        results = []
        for i in indices[0]:
            if i != -1 and i < len(self.metadata):
                results.append(self.metadata[i])
        
        return "\n---\n".join(results)