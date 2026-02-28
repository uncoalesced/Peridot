# core_system/command_router.py
# Engineered by uncoalesced.

import logging
import threading
import requests

logger = logging.getLogger("Peridot-Router")

# Add the server URL for research commands
SERVER_URL = "http://localhost:5000"


class CommandRouter:
    def __init__(self, core):
        self.core = core
        self.command_registry = {
            "help": self.help_command,
            "clear": self.clear_command,
            "status": self.status_command,
            "research": self.research_command,
            "exit": self.exit_command,
        }

    def route(self, command_name, args=""):
        # Normalize inputs
        command_name = command_name.lower().strip()

        if command_name in self.command_registry:
            try:
                return self.command_registry[command_name](args)
            except Exception as e:
                logger.error(f"Command Execution Failed: {e}")
                return f"[ERROR] Command '{command_name}' failed: {e}"

        return f"[SYSTEM] Unknown command: '{command_name}'. Type 'help' for options."

    # --- COMMAND HANDLERS ---

    def help_command(self, args):
        return (
            "AVAILABLE COMMANDS:\n"
            "-------------------\n"
            "help        - Show this menu\n"
            "clear       - Clear chat history\n"
            "status      - Show system vitals\n"
            "research    - Medical Research Controls\n"
            "  > enable  : Turn on auto-contribution (VRAM State Machine)\n"
            "  > disable : Turn off contribution\n"
            "  > status  : Check current Folding state\n"
            "exit        - Shutdown Peridot"
        )

    def clear_command(self, args):
        if self.core.ui:
            self.core.ui.chat_display.config(state="normal")
            self.core.ui.chat_display.delete(1.0, "end")
            self.core.ui.print_logo()
            self.core.ui.chat_display.config(state="disabled")
        self.core.chat_memory = []
        return "[SYSTEM] Memory & Screen Cleared."

    def status_command(self, args):
        # Check submodule status safely
        ears_status = (
            "ONLINE"
            if hasattr(self.core, "ears")
            and self.core.ears
            and self.core.ears.is_loaded
            else "OFFLINE"
        )

        # Ask server.py for research status
        research_status = "UNKNOWN"
        try:
            r = requests.get(
                f"{SERVER_URL}/research/status", timeout=5
            )  # Increased timeout
            if r.status_code == 200:
                data = r.json()
                if data.get("enabled"):
                    research_status = (
                        "FOLDING" if data.get("active") else "IDLE MONITORING"
                    )
                else:
                    research_status = "DISABLED"
        except:
            research_status = "SERVER DISCONNECTED"

        return (
            f"SYSTEM STATUS:\n"
            f"  > Audio:    [{ears_status}]\n"
            f"  > VRAM MGR: [{research_status}]\n"
            f"  > Brain:    [LINKED]"
        )

    def research_command(self, args):
        """
        Sends commands to the VRAM State Machine running in server.py
        """
        if not args:
            return "Usage: research [enable | disable | status]"

        cmd = args.split()[0].lower()

        try:
            if cmd == "enable":
                r = requests.post(
                    f"{SERVER_URL}/research/enable", timeout=5
                )  # Increased timeout
                return "Medical Research Module [ENABLED]. I will fold proteins when you are idle."

            elif cmd == "disable":
                r = requests.post(
                    f"{SERVER_URL}/research/disable", timeout=5
                )  # Increased timeout
                return "Medical Research Module [DISABLED]. VRAM is now locked to Inference."

            elif cmd == "status":
                r = requests.get(
                    f"{SERVER_URL}/research/status", timeout=5
                )  # Increased timeout
                data = r.json()
                state = "Folding" if data.get("active") else "Paused (Waiting for Idle)"
                enabled = "Yes" if data.get("enabled") else "No"
                return f"Research Engine Status:\n - Enabled: {enabled}\n - Current State: {state}"

            else:
                return f"Unknown research command: {cmd}"

        except requests.exceptions.RequestException:
            return "[ERROR] Could not communicate with the VRAM State Machine. Is server.py running?"

    def exit_command(self, args):
        self.core.shutdown()
        return "Shutting down..."
