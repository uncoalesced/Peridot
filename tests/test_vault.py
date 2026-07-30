import importlib
import sys
import types
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _vector_for(text: str) -> np.ndarray:
    vector = np.zeros(384, dtype=np.float32)
    lowered = text.lower()
    if "alpha" in lowered:
        vector[0] = 1.0
    elif "beta" in lowered:
        vector[1] = 1.0
    elif "gamma" in lowered:
        vector[2] = 1.0
    return vector


class DummyEmbedder:
    def embed_documents(self, texts):
        return np.stack([_vector_for(text) for text in texts]).astype(np.float32)


def _load_vault_module(monkeypatch):
    fake_embedder_module = types.SimpleNamespace(embedder=DummyEmbedder())
    monkeypatch.setitem(sys.modules, "core_system.memory.embedder", fake_embedder_module)

    from core_system.memory import turbovec_index

    monkeypatch.setattr(turbovec_index, "TURBOVEC_NATIVE", False)

    module = importlib.import_module("core_system.memory.vault")
    return importlib.reload(module)


def test_vault_add_search_save_load_delete_and_allowlist(tmp_path, monkeypatch):
    vault_module = _load_vault_module(monkeypatch)
    monkeypatch.setattr(vault_module, "STORAGE_PATH", tmp_path / "storage")
    monkeypatch.setattr(vault_module, "INPUT_PATH", tmp_path / "input")
    monkeypatch.setattr(vault_module, "PROCESSED_PATH", tmp_path / "processed")

    vault = vault_module.PersistentVault()
    assert vault.index.dim == 384
    assert vault.index.bit_width == 4

    assert vault.add_documents(["alpha text"], source="docA.pdf") == 1
    assert vault.add_documents(["beta text"], source="docB.pdf") == 1

    metadata_by_source = {meta["source"]: chunk_id for chunk_id, meta in vault.metadata.items()}
    alpha_id = metadata_by_source["docA.pdf"]
    beta_id = metadata_by_source["docB.pdf"]

    assert vault.index.list_ids() == [alpha_id, beta_id]
    assert vault.search(_vector_for("beta query"), top_k=1) == ["[SOURCE DOC: docB.pdf]\nbeta text"]
    assert vault.search(_vector_for("beta query"), top_k=1, allowlist=[alpha_id]) == [
        "[SOURCE DOC: docA.pdf]\nalpha text"
    ]

    vault.save_vault()
    reloaded = vault_module.PersistentVault()
    assert reloaded.metadata == vault.metadata
    assert reloaded.index.list_ids() == [alpha_id, beta_id]
    assert reloaded.search(_vector_for("beta query"), top_k=1) == ["[SOURCE DOC: docB.pdf]\nbeta text"]

    assert reloaded.delete_by_source("docA.pdf") == 1
    assert reloaded.index.list_ids() == [beta_id]
    assert list(reloaded.metadata) == [str(beta_id)]
    assert reloaded.search(_vector_for("beta query"), top_k=1) == ["[SOURCE DOC: docB.pdf]\nbeta text"]
