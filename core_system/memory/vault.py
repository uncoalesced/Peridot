# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | L2 PERSISTENT VAULT (TURBOVEC)
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------
"""
Layer 2 Persistent Vector Storage using TurboVec

TurboVec is a Rust-based vector index utilizing TurboQuant algorithms
for extreme memory compression (up to 16x reduction vs. FAISS).

Key features:
- IdMapIndex for stable chunk identifiers that survive deletions
- 4-bit quantization for memory efficiency
- 384-dimensional vectors (matching all-MiniLM-L6-v2 embedder)
- No pickle - uses safetensors for security
"""

import os
import sys
import logging
import json
try:
    import fitz
except ImportError:
    fitz = None
import shutil
import gc
from pathlib import Path
from typing import Dict, List, Optional

from core_system.audit import ghost
from core_system.memory.embedder import embedder
from core_system.memory.turbovec_index import IdMapIndex
from config import INPUT_PATH, PROCESSED_PATH, STORAGE_PATH

class PersistentVault:
    """
    Persistent vector storage layer using TurboVec IdMapIndex.

    Replaces FAISS-based implementation from v1.5.x with:
    - Stable chunk identifiers ([SOURCE DOC] tags) that survive deletions
    - 4-bit quantization for 16x memory compression
    - safetensors serialization (no pickle/RCE risk)
    """

    def __init__(self, dim: int = 384, bit_width: int = 4):
        """
        Initialize the PersistentVault.

        Args:
            dim: Vector dimension (384 for all-MiniLM-L6-v2)
            bit_width: Quantization bits (4 for extreme compression)
        """
        self.vault_path = STORAGE_PATH / "vector_db"
        self.vault_path.mkdir(parents=True, exist_ok=True)

        self.index_dir = self.vault_path / "turbovec_index"
        self.meta_file = self.vault_path / "vault_metadata.json"

        self.dimension = dim
        self.bit_width = bit_width

        # Initialize TurboVec IdMapIndex
        self.index = IdMapIndex(dim=dim, bit_width=bit_width)
        self.metadata: Dict[str, Dict[str, str]] = {}

        self._load_vault()

    def _load_vault(self) -> None:
        """Load existing vault from disk if available."""
        if self.index_dir.exists():
            try:
                # Load TurboVec index
                self.index.load(str(self.index_dir))

                # Load metadata
                if self.meta_file.exists():
                    with open(self.meta_file, "r", encoding="utf-8") as f:
                        self.metadata = json.load(f)

                ghost.info(f"VAULT | TurboVec Layer 2 Online. {self.index.size} sectors secured.")
            except Exception as e:
                ghost.error(f"VAULT | Corruption detected: {e}. Rebuilding index.")
                self.index = IdMapIndex(dim=self.dimension, bit_width=self.bit_width)
                self.metadata = {}
        else:
            ghost.info("VAULT | TurboVec Layer 2 Initialised (Empty).")

    def _chunk_ids_for_source(self, source: str, count: int) -> List[str]:
        existing_ids = set(self.index.list_ids()) if hasattr(self.index, "list_ids") else set()
        prefix = f"[SOURCE DOC: {source}]_chunk_"
        chunk_ids = []
        chunk_number = 0
        while len(chunk_ids) < count:
            chunk_id = f"{prefix}{chunk_number}"
            if chunk_id not in existing_ids:
                chunk_ids.append(chunk_id)
            chunk_number += 1
        return chunk_ids

    def add_documents(self, documents: List[str], source: str) -> int:
        prefix = f"[SOURCE DOC: {source}]\n"
        tagged_documents = [
            document if document.startswith(prefix) else f"{prefix}{document.strip()}"
            for document in documents
            if document.strip()
        ]
        if not tagged_documents:
            return 0

        chunk_ids = self._chunk_ids_for_source(source, len(tagged_documents))
        embeddings = embedder.embed_documents(tagged_documents)
        self.index.add_with_ids(embeddings, chunk_ids)

        if not isinstance(self.metadata, dict):
            self.metadata = {}
        for chunk_id, tagged_document in zip(chunk_ids, tagged_documents):
            self.metadata[chunk_id] = {
                "source": source,
                "text": tagged_document,
            }
        return len(chunk_ids)

    def save_vault(self) -> None:
        """Persist vault state to disk using safetensors format."""
        try:
            self.index.save(str(self.index_dir))

            # Save metadata as UTF-8 JSON
            with open(self.meta_file, "w", encoding="utf-8") as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)

            ghost.info("VAULT | State committed to disk (safetensors format).")
        except Exception as e:
            ghost.error(f"VAULT | Save failed: {e}")

    def chunk_and_tag_text(self, text: str, filename: str,
                            chunk_size: int = 400, overlap: int = 50) -> List[str]:
        """
        Split text into overlapping chunks with source provenance tags.

        Args:
            text: Raw document text
            filename: Source filename for provenance tagging
            chunk_size: Target words per chunk
            overlap: Overlapping words between chunks

        Returns:
            List of tagged chunks with [SOURCE DOC: filename] prefix
        """
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size - overlap):
            raw_chunk = " ".join(words[i:i + chunk_size])
            if raw_chunk.strip():
                # Burn the source filename into the chunk for provenance
                tagged_chunk = f"[SOURCE DOC: {filename}]\n{raw_chunk}"
                chunks.append(tagged_chunk)
        return chunks

    def ingest_file(self, pdf_path: Path) -> int:
        """
        Ingest a single PDF file into the vault.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Number of chunks ingested
        """
        try:
            full_text = ""
            with fitz.open(pdf_path) as doc:
                for page in doc:
                    # Layout preservation for accounting tables
                    full_text += page.get_text("text", sort=True) + "\n"

            chunks = self.chunk_and_tag_text(full_text, pdf_path.name)
            if not chunks:
                return 0

            count = self.add_documents(chunks, source=pdf_path.name)
            if count == 0:
                return 0

            gc.collect()

            # Move processed file
            PROCESSED_PATH.mkdir(parents=True, exist_ok=True)
            shutil.move(str(pdf_path), str(PROCESSED_PATH / pdf_path.name))

            ghost.info(f"VAULT | Ingested & Tagged: {pdf_path.name} ({count} chunks)")
            return count

        except Exception as e:
            ghost.error(f"VAULT | Ingestion failed for {pdf_path.name}: {e}")
            return 0

    def ingest_directory(self) -> None:
        """Ingest all PDF files from the INPUT_PATH directory."""
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

    def search(
        self,
        query_vector,
        top_k: int = 6,
        allowlist: Optional[List[str]] = None,
    ) -> Optional[List[str]]:
        """
        Search for semantically relevant chunks.

        Args:
            query_vector: Embedding vector from all-MiniLM-L6-v2
            top_k: Number of results to return

        Returns:
            List of relevant chunk texts, or None if no results found
        """
        if self.index.size == 0:
            return None

        try:
            distances, chunk_ids, scores = self.index.search(
                query_vector,
                k=top_k,
                allowlist=allowlist,
            )

            if len(chunk_ids) == 0:
                return None

            if len(distances) > 0 and distances[0] > 1.85:
                return None

            results = []
            if isinstance(self.metadata, dict):
                for chunk_id in chunk_ids:
                    metadata = self.metadata.get(str(chunk_id))
                    if isinstance(metadata, dict):
                        text = metadata.get("text")
                    else:
                        text = metadata
                    if text:
                        results.append(text)
            else:
                for index, _ in enumerate(chunk_ids):
                    if index < len(self.metadata):
                        results.append(self.metadata[index])

            ghost.info(f"VAULT | Retrieved {len(results)} chunks (best score: {scores[0]:.4f})")
            return results if results else None

        except Exception as e:
            ghost.error(f"VAULT | Search failed: {e}")
            return None

    def delete_by_source(self, filename: str) -> int:
        """
        Delete all chunks from a specific source document.

        Args:
            filename: The source filename to delete

        Returns:
            Number of chunks deleted
        """
        deleted = 0
        available_ids = self.index.list_ids() if hasattr(self.index, "list_ids") else []
        ids_to_delete = [
            chunk_id
            for chunk_id in available_ids
            if f"[SOURCE DOC: {filename}]" in chunk_id
        ]

        for chunk_id in ids_to_delete:
            if self.index.delete_by_id(chunk_id):
                deleted += 1

        if deleted > 0:
            if isinstance(self.metadata, dict):
                for chunk_id in ids_to_delete:
                    self.metadata.pop(chunk_id, None)
            else:
                self.metadata = [
                    meta for meta in self.metadata
                    if f"[SOURCE DOC: {filename}]" not in meta
                ]
            self.save_vault()
            ghost.info(f"VAULT | Deleted {deleted} chunks from {filename}")

        return deleted