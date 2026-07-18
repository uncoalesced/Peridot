import numpy as np

from core_system.memory import turbovec_index
from core_system.memory.turbovec_index import IdMapIndex


def test_fallback_delete_search_save_load_and_id_listing(tmp_path, monkeypatch):
    monkeypatch.setattr(turbovec_index, "TURBOVEC_NATIVE", False)

    index = IdMapIndex(dim=2, bit_width=4)
    index.add_with_ids(
        np.array([[0.0, 0.0], [10.0, 0.0]], dtype=np.float32),
        ["a", "b"],
    )

    assert index.list_ids() == ["a", "b"]
    assert index.delete_by_id("a") is True
    assert index.list_ids() == ["b"]

    distances, ids, scores = index.search(np.array([10.0, 0.0], dtype=np.float32), k=2)
    assert ids == ["b"]
    assert distances.tolist() == [0.0]
    assert scores == [1.0]

    index.save(str(tmp_path / "index"))
    loaded = IdMapIndex(dim=2, bit_width=4)
    loaded.load(str(tmp_path / "index"))

    assert loaded.list_ids() == ["b"]
    distances, ids, scores = loaded.search(np.array([10.0, 0.0], dtype=np.float32), k=2)
    assert ids == ["b"]
    assert distances.tolist() == [0.0]
    assert scores == [1.0]


def test_fallback_search_allowlist_and_mask(monkeypatch):
    monkeypatch.setattr(turbovec_index, "TURBOVEC_NATIVE", False)

    index = IdMapIndex(dim=2, bit_width=4)
    index.add_with_ids(
        np.array([[0.0, 0.0], [10.0, 0.0], [20.0, 0.0]], dtype=np.float32),
        ["a", "b", "c"],
    )

    distances, ids, _ = index.search(
        np.array([0.0, 0.0], dtype=np.float32),
        k=2,
        allowlist=["b", "c"],
    )
    assert ids == ["b", "c"]
    assert distances.tolist() == [10.0, 20.0]

    distances, ids, _ = index.search(
        np.array([0.0, 0.0], dtype=np.float32),
        k=2,
        mask=[False, True, False],
    )
    assert ids == ["b"]
    assert distances.tolist() == [10.0]
