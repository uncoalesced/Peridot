# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | COMMAND ROUTER
# Copyright (C) 2026 uncoalesced
# 
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import logging
import requests
from config import SERVER_HOST, SERVER_PORT, API_KEY

logger = logging.getLogger("Peridot-Router")

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
            "vault": self.vault_command,
            "ingest": self.ingest_command,
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
            "clear       - Clear the screen (stored history is kept)\n"
            "status      - Show system vitals\n"
            "ingest      - Scan and vectorize new PDFs in the input folder\n"
            "vault [Q]   - Search local PDFs for query [Q]\n"
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
        # Was `self.core.chat_memory = []`, an attribute PeridotCore stopped
        # having when conversation state moved to the chat ledger in Phase 4.
        # The assignment created a new unused attribute and cleared nothing,
        # while the message claimed memory had been wiped. Clearing the screen
        # is all this does, so that is all it now says. To actually start from
        # a blank history, open a new session from the UI's session drawer.
        return "[SYSTEM] Screen cleared. Conversation memory is unchanged."

    def ingest_command(self, args):
        """Triggers the Vault to scan the input directory and ingest new PDFs."""
        if self.core.ui:
            self.core.ui.display_system_message(">> Scanning input directory for unmapped documents...")
            self.core.ui.display_system_message(">> Vectorizing data on Ryzen CPU. Please wait...")
        
        try:
            self.core.vault.ingest_directory()
            sectors = self.core.vault.index.ntotal if self.core.vault.index else 0
            return f"[SYSTEM] Ingestion complete. Layer 2 Vault is online with {sectors} secured sectors."
        except Exception as e:
            logger.error(f"Ingestion failed: {e}")
            return f"[ERROR] Vault ingestion failed: {e}"

    def vault_command(self, args):
        """Triggers the Layer 2 PDF Vault search explicitly."""
        if not args:
            return "[SYSTEM] Please specify what you want to research in the vault (e.g., 'vault Tell me about the Riddler')."

        if self.core.ui:
            self.core.ui.display_system_message(f">> Initiating Layer 2 Vault Extraction for: '{args}'")

        # PersistentVault.search takes an embedding, not text -- this passed the
        # raw query string, so the command raised on every invocation and
        # route()'s catch-all reported it as a generic command failure. Embed
        # first, exactly as server.py's /ask path does.
        try:
            from core_system.memory.embedder import embedder
            query_vector = embedder.embed_query(args)
        except Exception as e:
            logger.error(f"Vault search embedding failed: {e}")
            return "[ERROR] Semantic memory is offline; vault search is unavailable."

        chunks = self.core.vault.search(query_vector)
        # search() returns a list of chunk texts; interpolating the list itself
        # would put a Python repr in the prompt.
        vault_context = "\n---\n".join(chunks) if chunks else None

        if vault_context:
            if self.core.ui:
                self.core.ui.display_system_message(">> Target Acquired. Injecting context into VRAM...")
            augmented_prompt = (
                f"Using ONLY the following verified data from the system vault, answer the query.\n"
                f"If the data does not contain the answer, say 'The vault does not contain information on this topic.'\n\n"
                f"VAULT DATA:\n{vault_context}\n\n"
                f"USER QUERY: {args}"
            )
            return self.core._ask_ai_isolated(augmented_prompt)
        else:
            return "No matching records found in the Layer 2 Vault for that query."

    def status_command(self, args):
        ears_status = (
            "ONLINE"
            if getattr(self.core, "ears", None) and self.core.ears.is_loaded
            else "OFFLINE"
        )
        
        vault_status = (
            f"ONLINE ({self.core.vault.index.ntotal} sectors)"
            if getattr(self.core, "vault", None) and self.core.vault.index
            else "OFFLINE"
        )
        
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
            f"  > L2 Vault: [{vault_status}]\n"
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