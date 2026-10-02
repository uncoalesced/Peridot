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

import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from core_system.audit import ghost

TURBOVEC_NATIVE = True

# Try to import the official TurboVec package
# If not available, fall back to pure-Python implementation
# The native path below calls add_with_ids/search/delete_by_id/get_vector_by_id/
# save/load/size. turbovec 0.7.1 (latest release, no longer pinned) instead exposes
# add_with_ids/search/remove/contains/write/load/prepare, so enabling it just
# because the import succeeds crashed the vault on first save/delete. Only use
# a build that actually has the API this wrapper speaks.
_REQUIRED_NATIVE_API = ("add_with_ids", "search", "delete_by_id", "get_vector_by_id", "save", "load", "size")
try:
    import turbovec
    _missing = [name for name in _REQUIRED_NATIVE_API if not hasattr(turbovec.IdMapIndex, name)]
    if _missing:
        TURBOVEC_NATIVE = False
        ghost.warning(
            f"TURBOVEC | Installed turbovec lacks {_missing}; using the vectorised numpy fallback."
        )
    else:
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
        # Pure-Python fallback storage: one contiguous row-per-vector matrix
        # (grown by doubling) so search is a single mat-vec, not a Python loop
        # over N vectors. Deleted rows stay in place and are masked out.
        self._matrix = np.empty((0, dim), dtype=np.float32)
        self._alive = np.empty(0, dtype=bool)
        self._sqnorm = np.empty(0, dtype=np.float32)  # cached ||row||^2
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
            rows = []
            for vec, chunk_id in zip(vectors, ids):
                if chunk_id not in self._id_to_idx:
                    idx = self._next_idx + len(rows)
                    self._id_to_idx[chunk_id] = idx
                    self._idx_to_id[idx] = chunk_id
                    rows.append(np.asarray(vec, dtype=np.float32).reshape(-1))
            if rows:
                self._append_rows(np.stack(rows))

            ghost.info(f"TURBOVEC | Added {len(ids)} vectors with stable IDs (total: {self._next_idx})")

    def _append_rows(self, rows: np.ndarray) -> None:
        start, end = self._next_idx, self._next_idx + len(rows)
        if end > len(self._matrix):
            capacity = max(end, 2 * len(self._matrix), 64)
            matrix = np.empty((capacity, self.dim), dtype=np.float32)
            matrix[:start] = self._matrix[:start]
            alive = np.zeros(capacity, dtype=bool)
            alive[:start] = self._alive[:start]
            sqnorm = np.zeros(capacity, dtype=np.float32)
            sqnorm[:start] = self._sqnorm[:start]
            self._matrix, self._alive, self._sqnorm = matrix, alive, sqnorm
        self._matrix[start:end] = rows
        self._alive[start:end] = True
        self._sqnorm[start:end] = np.einsum("ij,ij->i", rows, rows)
        self._next_idx = end

    def list_ids(self) -> list:
        if hasattr(self, "id_to_doc"):
            return list(self.id_to_doc.keys())
        if hasattr(self, "ids"):
            return list(self.ids)
        if hasattr(self, "_id_to_idx"):
            return list(self._id_to_idx.keys())
        if TURBOVEC_NATIVE and hasattr(self._native_index, "list_ids"):
            return list(self._native_index.list_ids())
        return []

    def search(
        self,
        query_vector: np.ndarray,
        k: int = 6,
        allowlist: Optional[List[str]] = None,
        mask: Optional[List[bool]] = None,
    ) -> Tuple[np.ndarray, List[str], List[float]]:
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
        result_limit = max(0, int(k))
        allowed_ids = set(allowlist) if allowlist is not None else None
        mask_values = list(mask) if mask is not None else None

        if TURBOVEC_NATIVE:
            # Unfiltered: exactly k. Filtered in Python below: the whole index,
            # since any k-prefix could be filtered away entirely.
            filtered = allowed_ids is not None or mask_values is not None
            candidate_count = max(result_limit, self.size) if filtered else result_limit
            try:
                if mask_values is None:
                    distances, ids = self._native_index.search(query_vector, k=candidate_count)
                else:
                    distances, ids = self._native_index.search(
                        query_vector,
                        k=candidate_count,
                        mask=mask_values,
                    )
            except TypeError:
                distances, ids = self._native_index.search(query_vector, k=candidate_count)

            result_pairs = []
            for distance, chunk_id in zip(distances, ids):
                chunk_id = str(chunk_id)
                index = self._id_to_idx.get(chunk_id)
                if allowed_ids is not None and chunk_id not in allowed_ids:
                    continue
                if mask_values is not None and (
                    index is None or index >= len(mask_values) or not mask_values[index]
                ):
                    continue
                result_pairs.append((float(distance), chunk_id))
                if len(result_pairs) == result_limit:
                    break

            result_distances = np.array([distance for distance, _ in result_pairs])
            result_ids = [chunk_id for _, chunk_id in result_pairs]
            result_scores = [1.0 / (1.0 + distance) for distance in result_distances]
            return result_distances, result_ids, result_scores

        q_vec = np.asarray(query_vector, dtype=np.float32).reshape(-1)
        n = self._next_idx
        valid = self._alive[:n].copy()
        if mask_values is not None:
            mask_arr = np.zeros(n, dtype=bool)
            usable = min(n, len(mask_values))
            mask_arr[:usable] = np.asarray(mask_values[:usable], dtype=bool)
            valid &= mask_arr
        if allowed_ids is not None:
            allow_arr = np.zeros(n, dtype=bool)
            allowed_idx = [self._id_to_idx[c] for c in allowed_ids if c in self._id_to_idx]
            allow_arr[allowed_idx] = True
            valid &= allow_arr

        n_valid = int(valid.sum())
        if result_limit == 0 or n_valid == 0:
            return np.array([]), [], []

        # Rank by ||m||^2 - 2 m.q (the ||q||^2 term is constant): one mat-vec
        # over the contiguous slice -- no fancy-index copy of the matrix -- with
        # filtered rows pushed to +inf. Exact distances only for the winners.
        approx = self._sqnorm[:n] - 2.0 * (self._matrix[:n] @ q_vec)
        approx[~valid] = np.inf
        if n_valid > result_limit:
            candidates = np.argpartition(approx, result_limit - 1)[:result_limit]
        else:
            candidates = np.flatnonzero(valid)
        exact = np.linalg.norm(self._matrix[candidates] - q_vec, axis=1)
        order = np.argsort(exact, kind="stable")
        top = candidates[order]

        result_distances = exact[order].astype(np.float64)
        result_ids = [self._idx_to_id[int(index)] for index in top]
        result_scores = [1.0 / (1.0 + float(distance)) for distance in result_distances]
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
                self._alive[idx] = False  # Row stays; masked out of search
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
                return self._matrix[idx].copy()
            return None

    @property
    def size(self) -> int:
        """Return the number of vectors in the index."""
        if TURBOVEC_NATIVE:
            return self._native_index.size
        else:
            return len(self._id_to_idx)

    @property
    def ntotal(self) -> int:
        """
        FAISS-compatible alias for `size`.

        This class stands in for a FAISS IndexIDMap, so callers reach for the
        FAISS spelling. Without this the `status` and `ingest` commands both
        died on AttributeError. Aliasing here fixes every caller at once and
        keeps the next FAISS-shaped access working too.
        """
        return self.size

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
            valid_vectors = [
                (idx, self._matrix[idx])
                for idx in np.flatnonzero(self._alive[:self._next_idx]).tolist()
                if idx in self._idx_to_id
            ]
            if valid_vectors:
                vector_array = np.stack([vec for _, vec in valid_vectors])
                save_file({"vectors": vector_array}, str(save_dir / "vectors.safetensors"))

            # Save ID mappings as JSON
            compact_id_to_idx = {
                self._idx_to_id[old_idx]: new_idx
                for new_idx, (old_idx, _) in enumerate(valid_vectors)
            }
            compact_idx_to_id = {
                new_idx: chunk_id
                for chunk_id, new_idx in compact_id_to_idx.items()
            }
            meta = {
                "id_to_idx": compact_id_to_idx,
                "idx_to_id": {str(k): v for k, v in compact_idx_to_id.items()},
                "dim": self.dim,
                "bit_width": self.bit_width,
                "next_idx": len(valid_vectors)
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
                matrix = np.ascontiguousarray(tensors["vectors"], dtype=np.float32)
                self._matrix = matrix
                self._alive = np.ones(len(matrix), dtype=bool)
                self._sqnorm = np.einsum("ij,ij->i", matrix, matrix)

            if meta_file.exists():
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                self._id_to_idx = meta["id_to_idx"]
                self._idx_to_id = {int(k): v for k, v in meta["idx_to_id"].items()}
                self._next_idx = meta["next_idx"]

            ghost.info(f"TURBOVEC | Index loaded from {path} (vectors: {self.size})")


# Export the main class
__all__ = ["IdMapIndex", "TURBOVEC_NATIVE"]