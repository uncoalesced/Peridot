# -----------------------------------------------------------------------------
# PERIDOT VAULT | Layer 2 Retrieval-Augmented Generation
# Copyright (C) 2026 uncoalesced
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import os
import sys
from pathlib import Path

# CRITICAL FIX: Force Python to recognize the Peridot root directory.
# This prevents ModuleNotFoundErrors when running ingest from PowerShell.
peridot_root = str(Path(__file__).parent.parent.parent.absolute())
if peridot_root not in sys.path:
    sys.path.insert(0, peridot_root)

import faiss
import pickle
import numpy as np
import fitz  # PyMuPDF
import shutil
import gc

# Import the centralized audit logger and the singleton CPU embedder
from core_system.audit import ghost
from core_system.memory.embedder import embedder
from config import INPUT_PATH, PROCESSED_PATH

class PersistentVault:
    def __init__(self):
        self.vault_path = PROCESSED_PATH
        self.index_file = self.vault_path / "peridot_vault.index"
        self.meta_file = self.vault_path / "peridot_vault.meta"
        
        # We know all-MiniLM-L6-v2 outputs exactly 384 dimensions
        self.dimension = 384
        
        self.index = None
        self.metadata = []  # Stores the actual text chunks
        self._load_vault()

    def _load_vault(self):
        """Loads the persistent FAISS index from disk."""
        if self.index_file.exists() and self.meta_file.exists():
            self.index = faiss.read_index(str(self.index_file))
            with open(self.meta_file, 'rb') as f:
                self.metadata = pickle.load(f)
            ghost.info(f"VAULT | Layer 2 Online. {self.index.ntotal} sectors secured.")
        else:
            self.index = faiss.IndexFlatL2(self.dimension)
            ghost.info("VAULT | Layer 2 Initialized (Empty).")

    def save_vault(self):
        """Commits the RAM index to disk."""
        # Ensure the directory exists before saving
        self.vault_path.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(self.index_file))
        with open(self.meta_file, 'wb') as f:
            pickle.dump(self.metadata, f)
        ghost.info("VAULT | State committed to disk.")

    def chunk_text(self, text, chunk_size=400, overlap=50):
        """Slices documents into overlapping context windows."""
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size - overlap):
            chunk = " ".join(words[i:i + chunk_size])
            if chunk:
                chunks.append(chunk)
        return chunks

    def ingest_file(self, pdf_path: Path) -> int:
        """Processes a single PDF file, vectorizes it, and moves it to processed."""
        try:
            full_text = ""
            # Strict context manager guarantees the file is released at the OS level
            with fitz.open(pdf_path) as doc:
                for page in doc:
                    full_text += page.get_text("text") + "\n"
            
            chunks = self.chunk_text(full_text)
            if not chunks:
                return 0
            
            # Use the global Ryzen-bound CPU embedder
            embeddings = embedder.embed_documents(chunks)
            
            self.index.add(embeddings)
            self.metadata.extend(chunks)
            
            # Force Python to destroy any lingering C-pointers to the file
            gc.collect()
            
            # Robust Windows file move
            PROCESSED_PATH.mkdir(parents=True, exist_ok=True)
            shutil.move(str(pdf_path), str(PROCESSED_PATH / pdf_path.name))
            ghost.info(f"VAULT | Ingested: {pdf_path.name}")
            
            return len(chunks)
            
        except Exception as e:
            ghost.error(f"VAULT | Ingestion failed for {pdf_path.name}: {e}")
            return 0

    def ingest_directory(self):
        """Scans the input folder and ingests all unmapped PDFs."""
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
        """
        Retrieves the most relevant facts from the Vault.
        Receives a pre-computed vector from the Router to prevent redundant CPU cycles.
        Returns a list of strings to inject into the LLM context.
        """
        if self.index is None or self.index.ntotal == 0:
            return None
            
        distances, indices = self.index.search(query_vector, top_k)
        
        # RELAXED DISTANCE THRESHOLD: Allows shorter queries to match longer text blocks
        if distances[0][0] > 1.85:  
            return None

        results = []
        for i in indices[0]:
            if i != -1 and i < len(self.metadata):
                results.append(self.metadata[i])
        
        return results if results else None

# --- COMMAND LINE INTERFACE ---
if __name__ == "__main__":
    vault = PersistentVault()
    
    if len(sys.argv) > 1 and sys.argv[1] == "ingest":
        if len(sys.argv) > 2:
            # Command: python core_system/memory/vault.py ingest "input/file.pdf"
            target_file = Path(sys.argv[2])
            if target_file.exists():
                chunks_added = vault.ingest_file(target_file)
                if chunks_added > 0:
                    vault.save_vault()
            else:
                print(f"File not found: {target_file}")
        else:
            # Command: python core_system/memory/vault.py ingest
            vault.ingest_directory()