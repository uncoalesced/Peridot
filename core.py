# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | CORE LOGIC
# Copyright (C) 2026 uncoalesced
# 
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import requests
import sys
import time
import os
import logging
import importlib

from core_system.enhancedlogger import logger
from core_system.command_router import CommandRouter
from core_system.research import MedicalResearchModule
from core_system.security import sanitize_input, load_constitution
from core_system.memory.vault import PersistentVault
from config import AI_SERVER_URL, SHUTDOWN_URL, API_KEY

from core_system.memory.chat_ledger import get_chat_ledger
from core_system.prompting.constitution import parse_kernel_response

ACTIVE_API_KEY = API_KEY

# A launch more than this far after the last message starts a fresh session
# instead of continuing the previous one.
SESSION_RESUME_WINDOW_S = int(os.getenv("SESSION_RESUME_WINDOW_S", str(6 * 3600)))

def safe_import(module_path, class_names):
    try:
        module = importlib.import_module(module_path)
        for name in class_names:
            if hasattr(module, name):
                return getattr(module, name)
    except Exception as e:
        logger.debug(f"Failed to import from {module_path}: {e}")
    return None

class PeridotCore:
    def __init__(self):
        self.logger = logger
        self.running = False
        self.ui = None
        self.ears = None
        self.last_interaction_time = time.time()
        self.current_session_id = None
        
        self.constitution = load_constitution()

        # Core Modules
        self.research = MedicalResearchModule(core=self)
        self.command_router = CommandRouter(core=self)
        
        # [v2.0] Layer 2 Persistent PDF Vault
        self.vault = PersistentVault()
        
        # Phase 4: Chat Ledger for persistent multi-session memory
        self.chat_ledger = get_chat_ledger()
        self._ensure_active_session()
        
        self.logger.info("Kernel logic initialised.", source="CORE")

    def _ensure_active_session(self):
        if self.current_session_id is None:
            # Resume only a *recent* session. The old code took the newest row
            # unconditionally, so one session created months ago kept winning
            # forever: every launch appended into it, its stale title stuck,
            # and its ancient turns were replayed as prompt context.
            sessions = self.chat_ledger.list_sessions(limit=1)
            if sessions and (time.time() - sessions[0]["updated_at"]) < SESSION_RESUME_WINDOW_S:
                self.current_session_id = sessions[0]["session_id"]
                self.logger.info(f"Resumed session: {self.current_session_id[:8]}", source="CORE")
            else:
                self.current_session_id = self.chat_ledger.create_session("New Session")
                self.logger.info(f"Created new session: {self.current_session_id[:8]}", source="CORE")

    def create_new_session(self, title: str = "New Session") -> str:
        self.current_session_id = self.chat_ledger.create_session(title)
        self.logger.info(f"Created new session: {self.current_session_id[:8]} - {title}", source="CORE")
        return self.current_session_id

    def switch_session(self, session_id: str) -> bool:
        session = self.chat_ledger.get_session(session_id)
        if session:
            self.current_session_id = session_id
            self.logger.info(f"Switched to session: {session_id[:8]}", source="CORE")
            return True
        return False

    def list_sessions(self, limit: int = 50):
        return self.chat_ledger.list_sessions(limit)

    def delete_session(self, session_id: str) -> bool:
        result = self.chat_ledger.delete_session(session_id)
        if result and session_id == self.current_session_id:
            self._ensure_active_session()
        return result

    def get_session_history(self, session_id: str = None, full: bool = False):
        sid = session_id or self.current_session_id
        if not sid:
            return []
        if full:
            return self.chat_ledger.get_full_history(sid)
        return self.chat_ledger.get_history(sid, limit=6)

    def start(self):
        if self.ui:
            self.ui.display_system_message("Initialising Peridot Kernel...")

        self._mount_subsystems()
        self.running = True
        
        if self.ui:
            self.ui.display_system_message(">> Neural Link: [ESTABLISHED]")
            self.ui.display_system_message(">> VRAM State Machine: [ACTIVE]")
            self.ui.display_system_message(">> Server-Side Routing: [ONLINE]")
            self.ui.display_system_message(">> Diagnostics: [OK]")
            self.ui.display_system_message("System Online. Waiting for input.")

    def _mount_subsystems(self):
        ears_class = safe_import("core_system.ears", ["PeridotEars"])
        if ears_class:
            try:
                self.ears = ears_class()
                self.ears.load_model_async(callback=lambda s: self._notify("Audio", s))
            except Exception as e:
                self.logger.error(f"Audio initialisation failed: {e}")
                self._notify("Audio", False, "Initialisation error")
        else:
            self._notify("Audio", False, "Module missing")

    def _notify(self, name, success, note=""):
        status = "ONLINE" if success else f"OFFLINE ({note})" if note else "FAILED"
        if self.ui:
            self.ui.display_system_message(f">> {name} Subsystem: [{status}]")

    def respond_to_input(self, text):
        if not text.strip():
            return

        self.last_interaction_time = time.time()
        
        clean_text, is_safe = sanitize_input(text)
        if not is_safe:
            self.logger.warning("Malicious input intercepted and destroyed.", source="SECURITY")
            return "[SECURITY BLOCK] Access Denied: Malicious code pattern detected. Incident logged."

        clean_text = clean_text.strip()
        
        if clean_text.lower() == "/ingest":
            self.logger.info("Manual ingestion sequence triggered.", source="CORE")
            try:
                self.vault.ingest_directory()
                return "Vault ingestion sequence completed. Check terminals for chunk metrics."
            except Exception as e:
                return f"[SYSTEM FAULT] Ingestion failed: {e}"

        parts = clean_text.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd in self.command_router.command_registry:
            return self.command_router.route(cmd, args) if args else self.command_router.route(cmd)

        response = self._ask_ai_with_memory(clean_text)
        
        return response

    def _ask_ai_with_memory(self, user_text):
        self._ensure_active_session()
        
        self.chat_ledger.add_message(self.current_session_id, "user", user_text)
        self._autotitle_session(user_text)

        history = self.chat_ledger.get_history(self.current_session_id, limit=6)
        
        prompt_segments = []
        for msg in history:
            role_header = "[USER]" if msg['role'] == 'user' else "[PERIDOT]"
            prompt_segments.append(f"{role_header}\n{msg['content']}\n")
            
        full_prompt = "\n".join(prompt_segments)

        response = self._send_to_server(query=user_text, prompt=full_prompt, session_id=self.current_session_id)
        
        if "[SYSTEM ERROR]" not in response and "[HTTP ERROR]" not in response:
            # Persist ONLY the answer body, never the [ANALYSIS] scaffolding or
            # a <think> fragment. Stored turns are replayed verbatim as
            # assistant turns on the next request, so a stored empty or
            # degenerate turn teaches the model in-context that a blank reply
            # is the house style. That feedback loop is what produced the
            # self-sustaining run of empty responses on 2026-08-20.
            _analysis, body = parse_kernel_response(response)
            if body and "[KERNEL FAULT]" not in body:
                self.chat_ledger.add_message(self.current_session_id, "assistant", body)
            else:
                self.logger.warning(
                    "Empty kernel body; turn not persisted to ledger.", source="CORE"
                )

        return response

    def _autotitle_session(self, user_text):
        """Name a session after its first real prompt instead of 'New Session'."""
        session = self.chat_ledger.get_session(self.current_session_id)
        if not session or session.get("title") != "New Session":
            return
        title = " ".join(user_text.split())[:48].strip()
        if title:
            self.chat_ledger.update_session_title(self.current_session_id, title)

    def _ask_ai_isolated(self, prompt):
        return self._send_to_server(query=prompt, prompt=prompt)

    def _send_to_server(self, query, prompt, session_id=None):
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {ACTIVE_API_KEY}"
            }
            
            payload = {"query": query, "prompt": prompt}
            if session_id:
                payload["session_id"] = session_id
            r = requests.post(AI_SERVER_URL, json=payload, headers=headers, timeout=900)
            r.raise_for_status()
            
            return r.json().get("response", "No response from brain.")
            
        except requests.exceptions.HTTPError as e:
            if r.status_code == 403:
                return "[SECURITY BLOCK] API Key rejected. Handshake failed. Ensure ACTIVE_API_KEY matches server."
            return f"[HTTP ERROR] {e}"
        except requests.exceptions.RequestException as e:
            return f"[SYSTEM ERROR] Link to Neural Engine severed: {e}"

    def shutdown(self):
        self.running = False
        if self.ui:
            self.ui.display_system_message("Severing Neural Link and Pausing Hardware...")

        if self.research:
            self.research.disable()

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {ACTIVE_API_KEY}"
            }
            requests.post(SHUTDOWN_URL, headers=headers, timeout=2)
        except Exception as e:
            pass

        sys.exit(0)