"""
Peridot Medical Research Module
================================
Enables GPU contribution to medical research (Cancer, Alzheimer's, etc.)
via Folding@Home when Peridot is idle.

Features:
- Auto-install FAHClient
- Auto-pause on user activity
- Statistics tracking
"""

import os
import sys
import subprocess
import threading
import time
import requests
import logging
import platform
import psutil

logger = logging.getLogger("Peridot-Research")


class MedicalResearchModule:
    def __init__(self, core):
        self.core = core
        self.enabled = False
        self.is_folding = False
        self.status = "DISABLED"

        # Paths
        self.fah_path = r"C:\Program Files (x86)\FAHClient\FAHClient.exe"
        self.config_path = os.path.join(os.getenv("APPDATA"), "FAHClient", "config.xml")

        # Identity
        self.user_name = "Peridot_User"
        self.team_id = "0"  # Default Team (We can make a 'Team Peridot' later)

    def check_installation(self):
        """Checks if Folding@Home is installed."""
        return os.path.exists(self.fah_path)

    def install_client(self):
        """Downloads and installs FAHClient silently."""
        logger.info("Downloading Folding@Home Installer...")
        url = "https://download.foldingathome.org/releases/public/release/fah-installer/windows-10-32bit/v7.6/fah-installer_7.6.21_x86.exe"
        installer = "fah_installer.exe"

        try:
            # Download
            r = requests.get(url, stream=True)
            with open(installer, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info("Running Installer (Accept Admin Prompt)...")
            # Run silent install
            subprocess.run([installer, "/S"], check=True)

            # Cleanup
            if os.path.exists(installer):
                os.remove(installer)

            logger.info("Folding@Home Installed Successfully.")
            return True
        except Exception as e:
            logger.error(f"Installation Failed: {e}")
            return False

    def configure(self):
        """Writes a config that allows remote control via Telnet."""
        config_xml = f"""<config>
          <allow v='127.0.0.1'/>
          <command-allow-no-pass v='127.0.0.1'/>
          
          <user v='{self.user_name}'/>
          <team v='{self.team_id}'/>
          
          <power v='medium'/>
          <gpu v='true'/>
          <slot id='0' type='GPU'/>
        </config>
        """
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w") as f:
                f.write(config_xml)
            logger.info("FAH Configured for Peridot Control.")
        except Exception as e:
            logger.error(f"Config Write Failed: {e}")

    def enable(self):
        """Turns on the module and starts the idle monitor."""
        if not self.check_installation():
            return False

        self.enabled = True
        self.status = "IDLE MONITORING"

        # Start the background monitor thread
        threading.Thread(target=self._monitor_loop, daemon=True).start()
        logger.info("Medical Research Module [ENABLED]")
        return True

    def disable(self):
        """Turns off the module and stops folding."""
        self.enabled = False
        self.pause()
        self.status = "DISABLED"
        logger.info("Medical Research Module [DISABLED]")

    def pause(self):
        """Pauses folding immediately."""
        if self.is_folding:
            self._send_cmd("pause")
            self.is_folding = False
            self.status = "PAUSED (AI Active)"
            logger.info("Research Paused.")

    def unpause(self):
        """Resumes folding."""
        if not self.enabled:
            return
        self._send_cmd("unpause")
        self.is_folding = True
        self.status = "FOLDING (Curing Disease)"
        logger.info("Research Resumed.")

    def _send_cmd(self, cmd):
        """Sends a command string to the FAHClient executable."""
        if not self.check_installation():
            return
        try:
            # Send command via flag
            subprocess.Popen(
                [self.fah_path, f"--send-{cmd}"],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception as e:
            logger.error(f"Command '{cmd}' failed: {e}")

    def _monitor_loop(self):
        """Background loop that checks for user idle time."""
        logger.info("Research Monitor Started.")
        while self.enabled:
            # Calculate idle time (Current Time - Last User Input Time)
            idle_seconds = time.time() - self.core.last_interaction_time

            # IDLE THRESHOLD: 300 seconds (5 minutes)
            if idle_seconds > 300 and not self.is_folding:
                self.unpause()

            # If user is active (idle < 5 mins) and we are folding -> STOP
            elif idle_seconds < 300 and self.is_folding:
                self.pause()

            # Check every 10 seconds
            time.sleep(10)

    def get_stats(self):
        """Returns a string summary of the module status."""
        state = "ACTIVE" if self.enabled else "DISABLED"
        folding = "YES" if self.is_folding else "NO"
        return f"Module: {state} | Folding Now: {folding} | Status: {self.status}"
