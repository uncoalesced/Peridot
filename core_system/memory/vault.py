# -----------------------------------------------------------------------------
# PERIDOT VAULT | Layer 2 Retrieval-Augmented Generation
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import os
import sys
import faiss
import json
import numpy as np
import fitz  # PyMuPDF
import shutil
import gc
from pathlib import Path

from core_system.audit import ghost
from core_system.memory.embedder import embedder
from config import INPUT_PATH, PROCESSED_PATH, STORAGE_PATH

class PersistentVault:
    def __init__(self):
        self.vault_path = STORAGE_PATH / "vector_db"
        self.vault_path.mkdir(parents=True, exist_ok=True)
        
        self.index_file = self.vault_path / "peridot_vault.index"
        self.meta_file = self.vault_path / "peridot_vault.meta"
        self.dimension = 384
        
        self.index = None
        self.metadata = []
        self._load_vault()

    def _load_vault(self):
        if self.index_file.exists() and self.meta_file.exists():
            try:
                self.index = faiss.read_index(str(self.index_file))
                # Enforce strict UTF-8 text reading for JSON
                with open(self.meta_file, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)
                ghost.info(f"VAULT | Layer 2 Online. {self.index.ntotal} sectors secured.")
            except Exception as e:
                ghost.error(f"VAULT | Corruption or Legacy format detected: {e}. Rebuilding DB.")
                self.index = faiss.IndexFlatL2(self.dimension)
                self.metadata = []
        else:
            self.index = faiss.IndexFlatL2(self.dimension)
            ghost.info("VAULT | Layer 2 Initialised (Empty).")

    def save_vault(self):
        faiss.write_index(self.index, str(self.index_file))
        # Enforce strict UTF-8 text writing for JSON
        with open(self.meta_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        ghost.info("VAULT | State committed to disk.")

    def chunk_and_tag_text(self, text, filename, chunk_size=400, overlap=50):
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size - overlap):
            raw_chunk = " ".join(words[i:i + chunk_size])
            if raw_chunk.strip():
                # INJECT METADATA: Burn the source filename into the vector
                tagged_chunk = f"[SOURCE DOC: {filename}]\n{raw_chunk}"
                chunks.append(tagged_chunk)
        return chunks

    def ingest_file(self, pdf_path: Path) -> int:
        try:
            full_text = ""
            with fitz.open(pdf_path) as doc:
                for page in doc:
                    # Layout preservation for accounting tables
                    full_text += page.get_text("text", sort=True) + "\n"
            
            chunks = self.chunk_and_tag_text(full_text, pdf_path.name)
            if not chunks: return 0
            
            embeddings = embedder.embed_documents(chunks)
            # Enforce strict float32 typing for FAISS C++ backend
            emb_matrix = np.array(embeddings).astype('float32')
            if len(emb_matrix.shape) == 1:
                emb_matrix = np.expand_dims(emb_matrix, axis=0)
                
            self.index.add(emb_matrix)
            self.metadata.extend(chunks)
            
            gc.collect()
            PROCESSED_PATH.mkdir(parents=True, exist_ok=True)
            shutil.move(str(pdf_path), str(PROCESSED_PATH / pdf_path.name))
            ghost.info(f"VAULT | Ingested & Tagged: {pdf_path.name}")
            return len(chunks)
        except Exception as e:
            ghost.error(f"VAULT | Ingestion failed for {pdf_path.name}: {e}")
            return 0

    def ingest_directory(self):
        if not INPUT_PATH.exists():
            INPUT_PATH.mkdir(parents=True, exist_ok=True)
            
        pdf_files = list(INPUT_PATH.glob("*.pdf"))
        if not pdf_files:
            ghost.info("VAULT | No new PDFs found in input directory.")
            return

        ghost.info(f"VAULT | Scanning {len(pdf_files)} documents for ingestion...")
        new_chunks = 0
        for pdf_path in pdf_files:
            new_chunks += self.ingest_file(pdf_path)

        if new_chunks > 0:
            self.save_vault()

    def search(self, query_vector: np.ndarray, top_k=3):
        if self.index is None or self.index.ntotal == 0:
            return None
            
        # Ensure query is float32 and 2D for FAISS
        q_vec = np.array(query_vector).astype('float32')
        if len(q_vec.shape) == 1:
            q_vec = np.expand_dims(q_vec, axis=0)
            
        distances, indices = self.index.search(q_vec, top_k)
        if distances[0][0] > 1.85:  
            return None

        results = []
        for i in indices[0]:
            if i != -1 and i < len(self.metadata):
                results.append(self.metadata[i])
        return results if results else None