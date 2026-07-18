# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | TURBOVEC INTEGRATION LAYER
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------
"""
TurboVec Integration Layer for Peridot v1.6.0+

This module provides a compatibility wrapper around the TurboVec Rust-based
vector index library. TurboVec uses TurboQuant algorithms for extreme memory
compression (up to 16x reduction) while maintaining retrieval accuracy.

Architecture:
- IdMapIndex: Supports stable chunk identifiers that survive deletions
- 4-bit quantization (bit_width=4) for extreme memory compression
- 384-dimensional vectors matching all-MiniLM-L6-v2 embedder output

When the official turbovec package is installed, this wrapper delegates to it.
For development/testing, a pure-Python fallback is provided.
"""

import os
import sys
import json
import struct
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from core_system.audit import ghost

# Try to import the official TurboVec package
# If not available, fall back to pure-Python implementation
try:
    import turbovec
    TURBOVEC_NATIVE = True
    ghost.info("TURBOVEC | Native Rust bindings loaded successfully.")
except ImportError:
    TURBOVEC_NATIVE = False
    ghost.warning("TURBOVEC | Native bindings not found. Using pure-Python fallback.")


class IdMapIndex:
    """
    TurboVec IdMapIndex wrapper for Peridot's persistent vector storage.

    Supports:
    - Stable chunk identifiers ([SOURCE DOC] tags) that survive deletions
    - 384-dimensional vectors with 4-bit quantization
    - Efficient L2 distance search

    When turbovec package is available, delegates to native Rust implementation.
    Otherwise, uses pure-Python fallback for development/testing.
    """

    def __init__(self, dim: int = 384, bit_width: int = 4):
        """
        Initialize the TurboVec index.

        Args:
            dim: Vector dimension (384 for all-MiniLM-L6-v2)
            bit_width: Quantization bits (4 for extreme compression)
        """
        self.dim = dim
        self.bit_width = bit_width
        self._id_to_idx: Dict[str, int] = {}  # Maps stable IDs to internal indices
        self._idx_to_id: Dict[int, str] = {}  # Maps internal indices to stable IDs
        self._vectors: List[np.ndarray] = []   # Stored vectors
        self._next_idx = 0

        if TURBOVEC_NATIVE:
            # Use native TurboVec implementation
            self._native_index = turbovec.IdMapIndex(dim=dim, bit_width=bit_width)
            ghost.info(f"TURBOVEC | Native IdMapIndex initialized (dim={dim}, bit_width={bit_width})")
        else:
            ghost.info(f"TURBOVEC | Pure-Python IdMapIndex initialized (dim={dim}, bit_width={bit_width})")

    def add_with_ids(self, vectors: np.ndarray, ids: List[str]) -> None:
        """
        Add vectors with stable identifiers to the index.

        Args:
            vectors: np.ndarray of shape (n, dim) - batch of vectors to add
            ids: List of stable string identifiers (e.g., "[SOURCE DOC: filename.pdf]_chunk_0")

        Note:
            Using stable IDs allows chunks to be individually deleted without
            corrupting index structure or losing provenance tracking.
        """
        if TURBOVEC_NATIVE:
            self._native_index.add_with_ids(vectors, ids)
        else:
            # Pure-Python fallback
            for vec, chunk_id in zip(vectors, ids):
                if chunk_id not in self._id_to_idx:
                    idx = self._next_idx
                    self._id_to_idx[chunk_id] = idx
                    self._idx_to_id[idx] = chunk_id
                    self._vectors.append(np.array(vec, dtype=np.float32))
                    self._next_idx += 1

            ghost.info(f"TURBOVEC | Added {len(ids)} vectors with stable IDs (total: {self._next_idx})")

    def search(self, query_vector: np.ndarray, k: int = 6) -> Tuple[np.ndarray, List[str], List[float]]:
        """
        Search for the k nearest neighbors.

        Args:
            query_vector: np.ndarray of shape (1, dim) or (dim,) - query embedding
            k: Number of results to return

        Returns:
            Tuple of (distances, ids, scores) where:
            - distances: np.ndarray of L2 distances
            - ids: List of stable chunk identifiers
            - scores: List of similarity scores (1 / (1 + distance))
        """
        if TURBOVEC_NATIVE:
            distances, ids = self._native_index.search(query_vector, k=k)
            scores = [1.0 / (1.0 + float(d)) for d in distances]
            return distances, list(ids), scores
        else:
            # Pure-Python fallback using L2 distance
            q_vec = np.array(query_vector, dtype=np.float32).flatten()
            if len(self._vectors) == 0:
                return np.array([]), [], []

            # Compute L2 distances to all vectors
            distances = []
            indices = []
            for idx, vec in enumerate(self._vectors):
                dist = np.linalg.norm(q_vec - vec)
                distances.append(dist)
                indices.append(idx)

            # Sort by distance and take top-k
            sorted_pairs = sorted(zip(distances, indices), key=lambda x: x[0])[:k]

            result_distances = np.array([d for d, _ in sorted_pairs])
            result_ids = [self._idx_to_id[idx] for _, idx in sorted_pairs]
            result_scores = [1.0 / (1.0 + float(d)) for d in result_distances]

            return result_distances, result_ids, result_scores

    def delete_by_id(self, chunk_id: str) -> bool:
        """
        Delete a vector by its stable identifier.

        Args:
            chunk_id: The stable identifier to delete

        Returns:
            True if deleted, False if not found

        Note:
            This is the key advantage of IdMapIndex over flat indices -
            we can delete individual entries without rebuilding.
        """
        if TURBOVEC_NATIVE:
            return self._native_index.delete_by_id(chunk_id)
        else:
            if chunk_id in self._id_to_idx:
                idx = self._id_to_idx[chunk_id]
                del self._id_to_idx[chunk_id]
                del self._idx_to_id[idx]
                self._vectors[idx] = None  # Mark as deleted
                ghost.info(f"TURBOVEC | Deleted chunk with ID: {chunk_id}")
                return True
            return False

    def get_vector_by_id(self, chunk_id: str) -> Optional[np.ndarray]:
        """Retrieve a vector by its stable identifier."""
        if TURBOVEC_NATIVE:
            return self._native_index.get_vector_by_id(chunk_id)
        else:
            if chunk_id in self._id_to_idx:
                idx = self._id_to_idx[chunk_id]
                return self._vectors[idx]
            return None

    @property
    def size(self) -> int:
        """Return the number of vectors in the index."""
        if TURBOVEC_NATIVE:
            return self._native_index.size
        else:
            return len(self._id_to_idx)

    def save(self, path: str) -> None:
        """
        Save the index to disk.

        Args:
            path: File path to save the index to

        Format:
            Uses .safetensors format for security (no pickle/RCE risk).
            Metadata stored as UTF-8 JSON alongside the index file.
        """
        if TURBOVEC_NATIVE:
            self._native_index.save(path)
        else:
            # Save index mapping and vectors using safetensors
            from safetensors.numpy import save_file
            import json

            save_dir = Path(path)
            save_dir.mkdir(parents=True, exist_ok=True)

            # Save vectors as numpy arrays in safetensors format
            valid_vectors = [(idx, vec) for idx, vec in enumerate(self._vectors) if vec is not None]
            if valid_vectors:
                vector_array = np.stack([vec for _, vec in valid_vectors])
                save_file({"vectors": vector_array}, str(save_dir / "vectors.safetensors"))

            # Save ID mappings as JSON
            meta = {
                "id_to_idx": self._id_to_idx,
                "idx_to_id": {str(k): v for k, v in self._idx_to_id.items()},
                "dim": self.dim,
                "bit_width": self.bit_width,
                "next_idx": self._next_idx
            }
            with open(save_dir / "metadata.json", "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

            ghost.info(f"TURBOVEC | Index saved to {path} (vectors: {self.size})")

    def load(self, path: str) -> None:
        """
        Load the index from disk.

        Args:
            path: File path to load the index from
        """
        if TURBOVEC_NATIVE:
            self._native_index.load(path)
        else:
            from safetensors.numpy import load_file
            import json

            load_dir = Path(path)
            if not load_dir.exists():
                ghost.warning(f"TURBOVEC | No existing index found at {path}")
                return

            # Load vectors
            vectors_file = load_dir / "vectors.safetensors"
            meta_file = load_dir / "metadata.json"

            if vectors_file.exists():
                tensors = load_file(str(vectors_file))
                self._vectors = [tensors["vectors"][i] for i in range(len(tensors["vectors"]))]

            if meta_file.exists():
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                self._id_to_idx = meta["id_to_idx"]
                self._idx_to_id = {int(k): v for k, v in meta["idx_to_id"].items()}
                self._next_idx = meta["next_idx"]

            ghost.info(f"TURBOVEC | Index loaded from {path} (vectors: {self.size})")


# Export the main class
__all__ = ["IdMapIndex", "TURBOVEC_NATIVE"]