# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
Build config/model_catalog.json from LLMFit's model database.

Source: mirror/llmfit/llmfit-core/data/hf_models.json
        (LLMFit, https://github.com/AlexsJones/llmfit, MIT, (c) 2026 Alex Jones)

Keeps text-generation entries that have GGUF sources (llama.cpp can run them),
drops embedding/feature-extraction/audio models, and writes compact rows that
core_system/modelfit.py reads. Stdlib only. Run:

    python scripts/build_model_catalog.py
"""

import datetime
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "mirror" / "llmfit" / "llmfit-core" / "data" / "hf_models.json"
DST = ROOT / "config" / "model_catalog.json"

TEXT_PIPELINES = {"text-generation", "unknown", "image-text-to-text", "any-to-any"}


def compact(e: dict) -> dict:
    row = {
        "name": e["name"],
        "params_b": round(e["parameters_raw"] / 1e9, 3),
        "ctx": e.get("context_length") or 4096,
        "use_case": e.get("use_case") or "",
        "repos": [s["repo"] for s in e["gguf_sources"]],
    }
    # Optional fields: only written when known, to keep the file small.
    for src, key in (("num_hidden_layers", "layers"), ("num_key_value_heads", "kv_heads"),
                     ("num_attention_heads", "heads"), ("head_dim", "head_dim"),
                     ("release_date", "date"), ("hf_downloads", "downloads")):
        if e.get(src):
            row[key] = e[src]
    if e.get("is_moe") and e.get("active_parameters"):
        row["active_b"] = round(e["active_parameters"] / 1e9, 3)
    return row


def keep(e: dict) -> bool:
    # Under 100M params is a toy (or a bad upstream count, e.g. a 7B listed as 0).
    if not e.get("gguf_sources") or (e.get("parameters_raw") or 0) < 1e8:
        return False
    if e.get("pipeline_tag") not in TEXT_PIPELINES:
        return False
    text = (e["name"] + " " + (e.get("use_case") or "")).lower()
    # MLX conversions are Apple-only weights even when a GGUF mirror exists.
    return not any(w in text for w in ("embedding", "embed", "rerank", "mlx"))


def main() -> None:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    rows = [compact(e) for e in data if keep(e)]
    out = {
        "_source": "LLMFit llmfit-core/data/hf_models.json (https://github.com/AlexsJones/llmfit)",
        "_license": "MIT, Copyright (c) 2026 Alex Jones. See THIRD_PARTY_NOTICES.md.",
        "_generated": datetime.date.today().isoformat(),
        "models": rows,
    }
    DST.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"[OK] {len(rows)} models -> {DST} ({DST.stat().st_size / 1024:.0f} KiB)")


if __name__ == "__main__":
    main()
