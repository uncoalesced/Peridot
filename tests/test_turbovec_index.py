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


def test_fallback_search_matches_brute_force(monkeypatch):
    """Vectorised search must return exactly the brute-force k nearest."""
    monkeypatch.setattr(turbovec_index, "TURBOVEC_NATIVE", False)
    rng = np.random.default_rng(7)
    vectors = rng.standard_normal((500, 16)).astype(np.float32)
    ids = [f"c{i}" for i in range(500)]

    index = IdMapIndex(dim=16, bit_width=4)
    index.add_with_ids(vectors[:300], ids[:300])
    index.add_with_ids(vectors[300:], ids[300:])  # exercises matrix growth
    deleted = set(range(0, 500, 9))
    for i in deleted:
        index.delete_by_id(ids[i])

    for q in rng.standard_normal((10, 16)).astype(np.float32):
        dist = np.linalg.norm(vectors - q, axis=1)
        live = [i for i in np.argsort(dist) if i not in deleted]
        distances, got, _ = index.search(q, k=6)
        assert got == [ids[i] for i in live[:6]]
        assert np.allclose(distances, dist[live[:6]], atol=1e-5)
