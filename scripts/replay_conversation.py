# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | CONVERSATION REPLAY (live check)
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# -----------------------------------------------------------------------------

"""Replay a list of prompts against a running Peridot server, like the UI does.

    venv\\Scripts\\python.exe scripts\\replay_conversation.py ["prompt" ...]

The server rebuilds history from the chat ledger by session_id, and the UI
(core.py) is what writes turns there, so this script does the same: a fresh
ledger session, the user turn written before each /ask, the answer written
after it only if constitution.is_storable_answer() accepts it.
"""

import argparse
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core_system.envfile import read_env  # noqa: E402
from core_system.memory.chat_ledger import get_chat_ledger  # noqa: E402
from core_system.prompting.constitution import is_storable_answer, parse_kernel_response  # noqa: E402

DEFAULT_PROMPTS = [
    "Hello there", "hows it going", "which model am I talking to",
    "How good are you at agentic tasks?", "can you use the web?", "what model?",
    "Look up Kid Cudi", "Tell me about his latest album's stats",
]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("prompts", nargs="*", default=DEFAULT_PROMPTS)
    ap.add_argument("--url", default="http://127.0.0.1:5000")
    ap.add_argument("--web", action="store_true", help="set the per-message web flag")
    args = ap.parse_args()

    key = read_env(ROOT / ".env").get("API_KEY", "")
    headers = {"Authorization": f"Bearer {key}"}
    ledger = get_chat_ledger()
    sid = ledger.create_session("replay " + time.strftime("%Y-%m-%d %H:%M:%S"))
    print(f"session {sid}\n")

    for prompt in args.prompts:
        ledger.add_message(sid, "user", prompt)
        started = time.monotonic()
        payload = {"query": prompt, "session_id": sid, **({"web": True} if args.web else {})}
        r = requests.post(f"{args.url}/ask", json=payload, headers=headers, timeout=900)
        data = r.json()
        answer = parse_kernel_response(data.get("response", ""))[1]
        reasoning = data.get("reasoning", "")
        stored = is_storable_answer(answer) and "[KERNEL FAULT]" not in answer
        if stored:
            ledger.add_message(sid, "assistant", answer, reasoning=reasoning or None)
        print(f">>> {prompt}")
        print(f"<<< {answer}")
        print(f"    [http {r.status_code} | {time.monotonic() - started:.1f}s | cancelled="
              f"{data.get('cancelled')} | reasoning {len(reasoning)} chars | stored={stored}"
              + (f" | notice: {data['notice']}" if data.get("notice") else "") + "]\n")


if __name__ == "__main__":
    main()
