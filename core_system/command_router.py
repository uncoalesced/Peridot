# core_system/command_router.py
# Engineered by uncoalesced.

import logging
import requests
from config import SERVER_HOST, SERVER_PORT, API_KEY

logger = logging.getLogger("Peridot-Router")

# Construct the secure base URL and auth headers
BASE_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

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
        command_name = command_name.lower().strip()

        if command_name in self.command_registry:
            try:
                return self.command_registry[command_name](args)
            except Exception as e:
                logger.error(f"Command Execution Failed: {e}")
                return f"[ERROR] Command '{command_name}' failed: {e}"

        return f"[SYSTEM] Unknown command: '{command_name}'. Type 'help' for options."

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
        ears_status = (
            "ONLINE"
            if getattr(self.core, "ears", None) and self.core.ears.is_loaded
            else "OFFLINE"
        )
        
        # Ping the server securely to check the hardware state
        research_status = "UNKNOWN"
        try:
            r = requests.get(f"{BASE_URL}/research/status", headers=HEADERS, timeout=5)
            if r.status_code == 200:
                data = r.json()
                if data.get("enabled"):
                    research_status = "FOLDING" if data.get("active") else "IDLE MONITORING"
                else:
                    research_status = "DISABLED"
            else:
                research_status = f"API ERROR ({r.status_code})"
        except requests.exceptions.RequestException:
            research_status = "SERVER DISCONNECTED"

        return (
            f"SYSTEM STATUS:\n"
            f"  > Audio:    [{ears_status}]\n"
            f"  > VRAM MGR: [{research_status}]\n"
            f"  > Brain:    [LINKED]"
        )

    def research_command(self, args):
        if not args:
            return "Usage: research [enable | disable | status]"

        cmd = args.split()[0].lower()

        try:
            if cmd == "enable":
                r = requests.post(f"{BASE_URL}/research/enable", headers=HEADERS, timeout=5)
                r.raise_for_status()
                return "Medical Research Module [ENABLED]. VRAM State Machine is armed."

            elif cmd == "disable":
                r = requests.post(f"{BASE_URL}/research/disable", headers=HEADERS, timeout=5)
                r.raise_for_status()
                return "Medical Research Module [DISABLED]. VRAM is now locked to Inference."

            elif cmd == "status":
                r = requests.get(f"{BASE_URL}/research/status", headers=HEADERS, timeout=5)
                r.raise_for_status()
                data = r.json()
                
                state = "Folding Active" if data.get("active") else "Paused (Waiting for Idle)"
                enabled = "Yes" if data.get("enabled") else "No"
                vram = data.get("vram_free", "Unknown")
                
                return f"Research Engine Status:\n - Enabled: {enabled}\n - State: {state}\n - Free VRAM: {vram}MB"

            else:
                return f"Unknown research command: {cmd}"
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Research command HTTP error: {e}")
            return "[ERROR] Could not communicate with the VRAM State Machine. Is server.py running?"

    def exit_command(self, args):
        self.core.shutdown()
        return "Shutting down..."