"""Peridot Sovereign Invocation -- approval dialog.

Reads {summary, task, timeout_s} as JSON on stdin, shows an always-on-top
Tk window, and prints exactly one JSON line to stdout:
    {"decision": "approve" | "deny", "text": "<possibly edited summary>"}
Deny on timeout, window close, or any failure.
"""

from __future__ import annotations

import json
import sys

BG = "#000000"
FG = "#EFF9F0"
ACCENT = "#00FF19"
SECONDARY = "#5F5AA2"
FONT = ("Segoe UI", 10)

_emitted = False


def emit(decision: str, text: str = "") -> None:
    global _emitted
    if _emitted:
        return
    _emitted = True
    sys.stdout.write(json.dumps({"decision": decision, "text": text}) + "\n")
    sys.stdout.flush()


def run(summary: str, task: str, timeout_s: int) -> None:
    import tkinter as tk

    root = tk.Tk()
    root.title("Peridot — Sovereign Invocation")
    root.configure(bg=BG)
    root.attributes("-topmost", True)
    root.geometry("620x460")
    root.minsize(420, 320)

    def finish(decision: str) -> None:
        emit(decision, summary_box.get("1.0", "end-1c") if decision == "approve" else "")
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", lambda: finish("deny"))

    tk.Label(root, text="A cloud agent asked Peridot to run this task:", bg=BG, fg=SECONDARY,
             font=FONT, anchor="w").pack(fill="x", padx=14, pady=(12, 2))
    short_task = task if len(task) <= 300 else task[:297] + "..."
    tk.Label(root, text=short_task, bg=BG, fg=FG, font=FONT, anchor="w", justify="left",
             wraplength=580).pack(fill="x", padx=14)

    tk.Label(root, text="Result to share (edit before approving):", bg=BG, fg=SECONDARY,
             font=FONT, anchor="w").pack(fill="x", padx=14, pady=(12, 2))
    summary_box = tk.Text(root, bg=BG, fg=FG, insertbackground=ACCENT, font=FONT, wrap="word",
                          highlightthickness=1, highlightbackground=SECONDARY,
                          highlightcolor=ACCENT, relief="flat")
    summary_box.insert("1.0", summary)

    bottom = tk.Frame(root, bg=BG)
    bottom.pack(side="bottom", fill="x", padx=14, pady=12)
    summary_box.pack(fill="both", expand=True, padx=14)

    countdown = tk.Label(bottom, bg=BG, fg=SECONDARY, font=FONT)
    countdown.pack(side="left")
    tk.Button(bottom, text="Deny", command=lambda: finish("deny"), bg=BG, fg=FG,
              activebackground=SECONDARY, activeforeground=FG, relief="flat",
              highlightthickness=1, highlightbackground=SECONDARY, padx=16
              ).pack(side="right", padx=(8, 0))
    tk.Button(bottom, text="Approve", command=lambda: finish("approve"), bg=ACCENT, fg=BG,
              activebackground=FG, activeforeground=BG, relief="flat", padx=16
              ).pack(side="right")

    remaining = [max(1, int(timeout_s))]

    def tick() -> None:
        if remaining[0] <= 0:
            finish("deny")
            return
        countdown.config(text=f"Auto-deny in {remaining[0]}s")
        remaining[0] -= 1
        root.after(1000, tick)

    tick()
    root.lift()
    root.focus_force()
    root.mainloop()


def main() -> None:
    try:
        req = json.loads(sys.stdin.read() or "{}")
        run(str(req.get("summary", "")), str(req.get("task", "")),
            int(req.get("timeout_s") or 120))
    except Exception as exc:
        print(f"[peridot-approve] {exc!r}", file=sys.stderr)
    emit("deny")  # no-op if a decision was already printed


if __name__ == "__main__":
    main()
