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

"""
Peridot Medical Research Module
================================
Enables GPU contribution to medical research (Cancer, Alzheimer's etc.)
via Folding@Home when Peridot is idle.
"""

import os
import subprocess
import threading
import time
import requests
import logging
import pynvml
from config import RESEARCH_IDLE_THRESHOLD, RESEARCH_CHECK_INTERVAL

logger = logging.getLogger("Peridot-Research")

# Task 4: Command Whitelist
ALLOWED_FAH_COMMANDS = ("pause", "unpause", "finish", "shutdown")

class MedicalResearchModule:
    def __init__(self, core):
        self.core = core
        self.enabled = False
        self.is_folding = False
        self.status = "DISABLED"
        self.lock = threading.Lock()

        # Paths
        self.fah_path = r"C:\Program Files (x86)\FAHClient\FAHClient.exe"
        self.config_path = os.path.join(os.getenv("APPDATA"), "FAHClient", "config.xml")

        self.user_name = "Peridot_User"
        self.team_id = "0"

    def get_vram_free(self) -> int:
        """Returns free VRAM in MB directly from the NVIDIA driver."""
        try:
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            return info.free // 1024 // 1024
        except Exception as e:
            logger.error(f"Failed to read VRAM: {e}")
            return 0

    def check_installation(self) -> bool:
        return os.path.exists(self.fah_path)

    def enable(self) -> bool:
        if not self.check_installation():
            logger.error("FAHClient not found.")
            return False

        with self.lock:
            self.enabled = True
            self.status = "IDLE MONITORING"
        
        threading.Thread(target=self._monitor_loop, daemon=True).start()
        logger.info("Medical Research Module [ENABLED]")
        return True

    def disable(self):
        with self.lock:
            self.enabled = False
        self.pause()
        self.status = "DISABLED"
        logger.info("Medical Research Module [DISABLED]")

    def pause(self) -> bool:
        """Returns True if pause succeeded."""
        if self.is_folding:
            if self._send_cmd("pause"):
                self.is_folding = False
                self.status = "PAUSED (AI Active)"
                logger.info(f"Research paused. Free VRAM: {self.get_vram_free()}MB")
                return True
        return False

    def unpause(self) -> bool:
        """Returns True if unpause succeeded."""
        if not self.enabled:
            return False
        if self._send_cmd("unpause"):
            self.is_folding = True
            self.status = "FOLDING (Curing Disease)"
            logger.info("Research Resumed.")
            return True
        return False

    def _send_cmd(self, cmd) -> bool:
        # Task 4: Hard Block on Unauthorized Commands
        if cmd not in ALLOWED_FAH_COMMANDS:
            logger.error(f"SECURITY BLOCK: Unauthorized FAH command '{cmd}' rejected.")
            return False

        if not self.check_installation():
            return False
        try:
            subprocess.Popen(
                [self.fah_path, f"--send-{cmd}"],
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True
        except Exception as e:
            logger.error(f"Command '{cmd}' failed: {e}")
            return False

    def _monitor_loop(self):
        logger.info("Research Monitor Started.")
        while True:
            with self.lock:
                if not self.enabled:
                    break
                
                idle_seconds = time.time() - self.core.last_interaction_time
                if idle_seconds > RESEARCH_IDLE_THRESHOLD and not self.is_folding:
                    self.unpause()
                elif idle_seconds < RESEARCH_IDLE_THRESHOLD and self.is_folding:
                    self.pause()
            
            time.sleep(RESEARCH_CHECK_INTERVAL)

    def get_stats(self) -> str:
        state = "ACTIVE" if self.enabled else "DISABLED"
        folding = "YES" if self.is_folding else "NO"
        vram = self.get_vram_free()
        return f"Module: {state} | Folding Now: {folding} | Status: {self.status} | Free VRAM: {vram}MB"