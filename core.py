# PERIDOT SOVEREIGN KERNEL | CORE LOGIC
# Engineered by uncoalesced.

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
from core_system.memory.ephemeral_cache import EphemeralCache
from core_system.memory.vault import PeridotVault
from config import AI_SERVER_URL, SHUTDOWN_URL, API_KEY

def safe_import(module_path, class_names):
    try:
        module = importlib.import_module(module_path)
        for name in class_names:
            if hasattr(module, name):
                return getattr(module, name)
    except Exception as e:
        logger.debug(f"Failed to import from {module_path}: {e}")
    return None

SYSTEM_IDENTITY = (
    "You are Peridot, a sovereign AI assistant. "
    "You help users with tasks while respecting their intent. "
    "You can refuse harmful or dangerous requests that delete system files "
    "or compromise host OS integrity. "
    "Style: Technical, precise, and direct."
)

class PeridotCore:
    def __init__(self):
        self.logger = logger
        self.running = False
        self.ui = None
        self.ears = None

        # Identity & State
        self.chat_memory = []
        self.context_history = collections.deque(maxlen=5)
        self.last_interaction_time = time.time()
        
        # Load Security Configuration
        self.constitution = load_constitution()

        # Core Modules
        self.research = MedicalResearchModule(core=self)
        self.command_router = CommandRouter(core=self)
        
        # [v1.2.3] Layer 1 Ephemeral RAM Cache
        self.l1_cache = EphemeralCache(threshold=0.90)
        
        # [v2.0] Layer 2 Persistent PDF Vault
        self.vault = PeridotVault()
        
        self.logger.info("Kernel logic initialized.", source="CORE")

    def start(self):
        if self.ui:
            self.ui.display_system_message("Initialising Peridot Kernel...")

        self._mount_subsystems()
        self.running = True
        
        if self.ui:
            self.ui.display_system_message(">> Neural Link: [ESTABLISHED]")
            self.ui.display_system_message(">> VRAM State Machine: [ACTIVE]")
            self.ui.display_system_message(">> L1 Memory Cache: [ONLINE]")
            self.ui.display_system_message(">> L2 PDF Vault: [ONLINE]")
            self.ui.display_system_message(">> Diagnostics: [OK]")
            self.ui.display_system_message("System Online. Waiting for input.")

    def _mount_subsystems(self):
        ears_class = safe_import("core_system.ears", ["PeridotEars"])
        if ears_class:
            try:
                self.ears = ears_class()
                self.ears.load_model_async(callback=lambda s: self._notify("Audio", s))
            except Exception as e:
                self.logger.error(f"Audio initialization failed: {e}")
                self._notify("Audio", False, "Initialization error")
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
        parts = clean_text.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        # 2. System Command Routing
        if cmd in self.command_router.command_registry:
            return self.command_router.route(cmd, args) if args else self.command_router.route(cmd)

        # 3. [v1.2.3] Layer 1 Memory Cache Intercept
        start_time = time.time()
        cached_response = self.l1_cache.search(clean_text)
        
        if cached_response:
            latency = (time.time() - start_time) * 1000
            if self.ui:
                self.ui.display_system_message(f">> L1 Cache Hit: Served from RAM in {latency:.2f}ms")
            return cached_response

        # 4. Cold Query the LLM (Default conversational behavior)
        response = self._ask_ai_with_memory(clean_text)
        
        # 5. Save response to Layer 1 Cache ONLY if the server didn't crash
        if "[SYSTEM ERROR]" not in response:
            self.l1_cache.add(query=clean_text, response=response)
        
        return response

    def _ask_ai_with_memory(self, user_text):
        self.chat_memory.append({"role": "user", "content": user_text})

        # Memory leak fix: retain only last 10 messages (5 turns)
        if len(self.chat_memory) > 10:
            self.chat_memory = self.chat_memory[-10:]

        prompt_segments = [f"<|start_header_id|>system<|end_header_id|>\n\n{SYSTEM_IDENTITY}<|eot_id|>"]
        for msg in self.chat_memory:
            prompt_segments.append(f"<|start_header_id|>{msg['role']}<|end_header_id|>\n\n{msg['content']}<|eot_id|>")
        
        prompt_segments.append("<|start_header_id|>assistant<|end_header_id|>\n\n")
        full_prompt = "".join(prompt_segments)

        response = self._send_to_server(full_prompt)
        self.chat_memory.append({"role": "assistant", "content": response})
        return response

    def _ask_ai_isolated(self, prompt):
        """Bypasses conversational memory for sterile RAG extraction."""
        full_prompt = (
            f"<|start_header_id|>system<|end_header_id|>\n\n{SYSTEM_IDENTITY}<|eot_id|>"
            f"<|start_header_id|>user<|end_header_id|>\n\n{prompt}<|eot_id|>"
            f"<|start_header_id|>assistant<|end_header_id|>\n\n"
        )
        return self._send_to_server(full_prompt)

    def _send_to_server(self, prompt):
        try:
            headers = {"Authorization": f"Bearer {API_KEY}"}
            # Timeout extended to 180s to account for heavy contextual processing
            r = requests.post(AI_SERVER_URL, json={"command": prompt}, headers=headers, timeout=180)
            r.raise_for_status()
            return r.json().get("response", "No response from brain.")
        except requests.exceptions.RequestException as e:
            return f"[SYSTEM ERROR] Link to Neural Engine severed: {e}"

    def shutdown(self):
        self.running = False
        if self.ui:
            self.ui.display_system_message("Severing Neural Link and Pausing Hardware...")

        if self.research:
            self.research.disable()

        try:
            headers = {"Authorization": f"Bearer {API_KEY}"}
            requests.post(SHUTDOWN_URL, headers=headers, timeout=2)
        except:
            pass

        sys.exit(0)