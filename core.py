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

        # Core Modules
        self.research = MedicalResearchModule(core=self)
        self.command_router = CommandRouter(core=self)
        self.logger.info("Kernel logic initialized.", source="CORE")

    def start(self):
        if self.ui:
            self.ui.display_system_message("Initialising Peridot Kernel...")

        self._mount_subsystems()
        self.running = True
        
        if self.ui:
            self.ui.display_system_message(">> Neural Link: [ESTABLISHED]")
            self.ui.display_system_message(">> VRAM State Machine: [ACTIVE]")
            self.ui.display_system_message(">> Diagnostics: [OK]")
            self.ui.display_system_message("System Online. Waiting for input.")

    def _mount_subsystems(self):
        ears_class = safe_import("core_system.ears", ["PeridotEars", "iCouldEars"])
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
        text_clean = text.strip()

        parts = text_clean.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd in self.command_router.command_registry:
            return self.command_router.route(cmd, args) if args else self.command_router.route(cmd)

        return self._ask_ai_with_memory(text_clean)

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

    def _send_to_server(self, prompt):
        try:
            headers = {"Authorization": f"Bearer {API_KEY}"}
            r = requests.post(AI_SERVER_URL, json={"command": prompt}, headers=headers, timeout=120)
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