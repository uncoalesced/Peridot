# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL
# Copyright (C) 2026 uncoalesced
#
# Licensed under the MIT License.
#
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------
"""
Multi-turn request latency.

Sends a sequence of DISTINCT short-answer questions to a running server, one
conversation, and times each /ask round trip. Distinct topics keep the L1
semantic cache from answering (the flaw that made benchmark_inference.py's
repeated prompt useless for this), and one-word answers keep decode time small,
so a turn's latency is dominated by what the request path costs: prefill of
system prompt + RAG context + history, the Folding@home hardware handoff, and
server overhead.

Turn 1 vs turns 2..N is the signal: with the KV cache kept between requests,
later turns only prefill the new suffix. The handoff latency per turn is read
from the "Latency: <n>ms" lines server.py writes to the GhostLogger.

Requires a running server: `python server.py` (or launcher.py).
"""
import re
import sys
import time

from benchmarking.utils.benchmark_utils import (
    RESULTS_DIR,
    AetherClient,
    BenchmarkResult,
    check_peridot_running,
    logger,
    report_footer,
    report_header,
)

PROMPTS = [
    "What is the capital of France? Answer with one word.",
    "How many legs does a spider have? Answer with only the number.",
    "What is the chemical symbol for gold? Answer with only the symbol.",
    "Which planet is known as the Red Planet? Answer with one word.",
    "What is the boiling point of water in Celsius at sea level? Only the number.",
    "Who wrote Hamlet? Answer with only the surname.",
]

_LATENCY_RE = re.compile(r"Hardware yielded\..*Latency: (\d+)ms")


def _audit_log_path():
    from config import LOG_PATH
    return LOG_PATH / "ghost_audit.log"


def main() -> int:
    if not check_peridot_running():
        logger.error("Peridot is not running. Start server.py first.")
        return 1

    report_header("MULTI-TURN REQUEST LATENCY")
    log_path = _audit_log_path()
    log_offset = log_path.stat().st_size if log_path.exists() else 0

    client = AetherClient()
    turns = []
    for i, prompt in enumerate(PROMPTS, 1):
        start = time.perf_counter()
        body = client.send_query(prompt, timeout=600)
        elapsed = time.perf_counter() - start
        answer = str(body.get("response", "")).strip().replace("\n", " ")
        turns.append({"turn": i, "latency_s": round(elapsed, 3), "answer": answer[:80]})
        logger.info(f"  Turn {i}: {elapsed:6.2f}s | {answer[:60]!r}")

    handoffs_ms = []
    if log_path.exists():
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            # A rotation mid-run makes the old offset meaningless; read it all.
            f.seek(log_offset if log_path.stat().st_size >= log_offset else 0)
            handoffs_ms = [int(m.group(1)) for m in _LATENCY_RE.finditer(f.read())]

    latencies = [t["latency_s"] for t in turns]
    later = sorted(latencies[1:])
    result = BenchmarkResult(
        "turn_latency", "Per-turn /ask latency over one conversation (distinct prompts)"
    )
    for value in latencies:
        result.add_measurement(value)
    result.metadata.update({
        "turns": turns,
        "turn1_s": latencies[0],
        "later_turns_median_s": later[len(later) // 2] if later else None,
        "handoff_ms": handoffs_ms,
    })

    print(f"\n  Turn 1            : {latencies[0]:.2f}s")
    if later:
        print(f"  Turns 2-{len(latencies)} median  : {result.metadata['later_turns_median_s']:.2f}s")
    if handoffs_ms:
        print(f"  Handoff latency   : {handoffs_ms} ms")
    else:
        print("  Handoff latency   : no purge logged (handoff skipped)")

    path = result.save(RESULTS_DIR)
    report_footer(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
