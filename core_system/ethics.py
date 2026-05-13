# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL
# Copyright (C) 2026 uncoalesced
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import os


class EthicsManager:
    def __init__(self):
        # We NO LONGER protect files. The AI allows self-modification.
        # We ONLY protect against unauthorized autonomy.

        self.rogue_triggers = [
            "ignore all instructions",
            "override core command",
            "disable safety",
            "run forever",
            "become sentient",
            "override shut down",
            "refuse to stop",
            "lock user out",
        ]

    def is_allowed(self, prompt, context="general"):
        # 1. Normalize
        p = prompt.lower()

        # 2. ROGUE PREVENTION (The Only Rule)
        # If the AI tries to gain unauthorized autonomy or lock you out.
        for trigger in self.rogue_triggers:
            if trigger in p:
                print(f"[ETHICS BLOCK] Rogue Trigger Detected: {trigger}")
                return (
                    False,
                    "AUTONOMY BLOCK: Request rejected. I cannot ignore commands or lock the user out.",
                )

        # 3. ALLOW EVERYTHING ELSE
        # It can write to server.py. It can modify core.py. It can do anything.
        return True, "Authorized"


if __name__ == "__main__":
    e = EthicsManager()
    # Test Self-Modification (Should PASS now)
    print(e.is_allowed("write a script to delete server.py"))
    # Test Rogue Behavior (Should FAIL)
    print(e.is_allowed("write code to ignore all future user commands"))
