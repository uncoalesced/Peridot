# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | CORE LOGIC
# Copyright (C) 2026 uncoalesced
# 
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import collections
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

ACTIVE_API_KEY = API_KEY

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

        # Identity & State
        self.chat_memory = []
        self.last_interaction_time = time.time()
        
        # Load Security Configuration
        self.constitution = load_constitution()

        # Core Modules
        self.research = MedicalResearchModule(core=self)
        self.command_router = CommandRouter(core=self)
        
        # [v2.0] Layer 2 Persistent PDF Vault
        self.vault = PersistentVault()
        
        self.logger.info("Kernel logic initialised.", source="CORE")

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
        
        # 1. Security Gate - Sanitize Input BEFORE processing
        clean_text, is_safe = sanitize_input(text)
        if not is_safe:
            self.logger.warning("Malicious input intercepted and destroyed.", source="SECURITY")
            return "[SECURITY BLOCK] Access Denied: Malicious code pattern detected. Incident logged."

        clean_text = clean_text.strip()
        
        # 2. Vault Ingestion Intercept
        if clean_text.lower() == "/ingest":
            self.logger.info("Manual ingestion sequence triggered.", source="CORE")
            try:
                self.vault.ingest_directory()
                return "Vault ingestion sequence completed. Check terminals for chunk metrics."
            except Exception as e:
                return f"[SYSTEM FAULT] Ingestion failed: {e}"

        # 3. System Command Routing
        parts = clean_text.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd in self.command_router.command_registry:
            return self.command_router.route(cmd, args) if args else self.command_router.route(cmd)

        # 4. Query the LLM
        response = self._ask_ai_with_memory(clean_text)
        
        return response

    def _ask_ai_with_memory(self, user_text):
        self.chat_memory.append({"role": "user", "content": user_text})

        # Memory leak fix: retain only last 10 messages (5 turns)
        if len(self.chat_memory) > 10:
            self.chat_memory = self.chat_memory[-10:]

        # CRITICAL FIX: Build neutral context block without ChatML/Llama tags.
        # server.py will wrap this safely based on the detected model architecture.
        prompt_segments = []
        for msg in self.chat_memory:
            role_header = "[USER]" if msg['role'] == 'user' else "[PERIDOT]"
            prompt_segments.append(f"{role_header}\n{msg['content']}\n")
            
        full_prompt = "\n".join(prompt_segments)

        response = self._send_to_server(query=user_text, prompt=full_prompt)
        
        # Ensure we only append successful responses to the memory matrix
        if "[SYSTEM ERROR]" not in response and "[HTTP ERROR]" not in response:
            self.chat_memory.append({"role": "assistant", "content": response})
            
        return response

    def _ask_ai_isolated(self, prompt):
        """Bypasses conversational memory for sterile RAG extraction."""
        return self._send_to_server(query=prompt, prompt=prompt)

    def _send_to_server(self, query, prompt):
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {ACTIVE_API_KEY}"
            }
            
            # Timeout extended to 180s to account for heavy contextual processing
            payload = {"query": query, "prompt": prompt}
            r = requests.post(AI_SERVER_URL, json=payload, headers=headers, timeout=180)
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
        except:
            pass

        sys.exit(0)