# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | CORE LOGIC
# Copyright (C) 2026 uncoalesced
# 
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import inspect
import json
import requests
import sys
import time
import os
import importlib

from core_system.enhancedlogger import logger
from core_system.command_router import CommandRouter
from core_system.research import MedicalResearchModule
from core_system.security import MAX_INPUT_CHARS, sanitize_input, load_constitution
from config import AI_SERVER_URL, SHUTDOWN_URL, API_KEY, SERVER_HOST, SERVER_PORT

from core_system.memory.chat_ledger import get_chat_ledger
from core_system.prompting.constitution import parse_kernel_response, stream_visible_body

try:  # newer constitution: refuses degenerate answers before they reach the ledger
    from core_system.prompting.constitution import is_storable_answer
except ImportError:
    is_storable_answer = None

ACTIVE_API_KEY = API_KEY
INGEST_URL = f"http://{SERVER_HOST}:{SERVER_PORT}/ingest"
STREAM_URL = f"http://{SERVER_HOST}:{SERVER_PORT}/ask/stream"
SETTINGS_URL = f"http://{SERVER_HOST}:{SERVER_PORT}/settings"
CANCEL_URL = f"http://{SERVER_HOST}:{SERVER_PORT}/ask/cancel"

# stream_visible_body() rescans the whole accumulated reply, so calling it per
# token is O(n^2) over a reply. The UI pumps at ~30 Hz, so recomputing more
# often than that is wasted: bound it to one scan per interval instead.
STREAM_EMIT_S = 0.03


def _settings_request(method, body=None, timeout=10):
    """GET/POST /settings. Always a dict: the settings, or {"error": str}."""
    try:
        r = requests.request(method, SETTINGS_URL, json=body, timeout=timeout,
                             headers={"Authorization": f"Bearer {ACTIVE_API_KEY}"})
    except requests.exceptions.RequestException as e:
        return {"error": f"engine unreachable: {e}"}
    try:
        data = r.json()
    except ValueError:
        data = None
    if not isinstance(data, dict):
        return {"error": f"HTTP {r.status_code}: unexpected reply"}
    if r.status_code != 200:
        return {"error": str(data.get("error") or f"HTTP {r.status_code}")}
    return data


def _notify(on_notice, notice):
    if on_notice is not None and notice:
        on_notice(str(notice))


def _final(on_final, data):
    """Hand the reply's metadata (model reasoning, whether it was stopped) to on_final."""
    if on_final is not None:
        on_final({"reasoning": str(data.get("reasoning") or ""),
                  "cancelled": bool(data.get("cancelled"))})


def post_cancel():
    """POST /ask/cancel. True when the engine stopped an in-flight reply. Never raises."""
    try:
        r = requests.post(CANCEL_URL, timeout=5,
                          headers={"Authorization": f"Bearer {ACTIVE_API_KEY}"})
        return r.status_code == 200 and bool(r.json().get("cancelled"))
    except Exception:
        return False


def get_settings():
    """All server settings, or {"error": str}. Never raises."""
    return _settings_request("GET", timeout=5)


def post_settings(changes):
    """POST changes; the server is the only writer. Returns the full updated
    settings, or {"error": str}. Never raises."""
    return _settings_request("POST", changes)

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
        
        # [v2.0] Layer 2 Persistent PDF Vault -- owned by the server process.
        # Loaded here lazily, only for the `vault <query>` command (see the
        # `vault` property): building it pulls torch + sentence-transformers
        # into the UI process at startup for nothing else.
        self._vault = None

        # Phase 4: Chat Ledger for persistent multi-session memory
        self.chat_ledger = get_chat_ledger()
        self._ensure_active_session()
        
        self.logger.info("Kernel logic initialised.", source="CORE")

    @property
    def vault(self):
        if self._vault is None:
            from core_system.memory.vault import PersistentVault
            self._vault = PersistentVault()
        return self._vault

    def ingest_via_server(self) -> int:
        """Run ingestion in the server process, which owns the searched index.

        Ingesting into a UI-side PersistentVault wrote to disk but left the
        server's in-memory index stale, so new documents were invisible to RAG
        until the server restarted. Returns the server's sector count.
        """
        headers = {"Authorization": f"Bearer {ACTIVE_API_KEY}"}
        r = requests.post(INGEST_URL, headers=headers, timeout=3600)
        r.raise_for_status()
        return r.json().get("sectors", 0)

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
                # Whisper loads on the first voice command, not at startup.
                if self.ui:
                    self.ui.display_system_message(">> Audio Subsystem: [STANDBY - loads on first use]")
            except Exception as e:
                self.logger.error(f"Audio initialisation failed: {e}")
                self._notify("Audio", False, "Initialisation error")
        else:
            self._notify("Audio", False, "Module missing")

    def _notify(self, name, success, note=""):
        status = "ONLINE" if success else f"OFFLINE ({note})" if note else "FAILED"
        if self.ui:
            self.ui.display_system_message(f">> {name} Subsystem: [{status}]")

    def respond_to_input(self, text, on_delta=None, on_tool=None, web=False, on_notice=None,
                         on_final=None):
        if not text.strip():
            return

        self.last_interaction_time = time.time()
        
        clean_text, is_safe = sanitize_input(text)
        if not is_safe:
            self.logger.warning("Oversized input rejected.", source="SECURITY")
            return f"[INPUT REJECTED] Message exceeds the {MAX_INPUT_CHARS:,}-character limit."

        clean_text = clean_text.strip()
        
        if clean_text.lower() == "/ingest":
            self.logger.info("Manual ingestion sequence triggered.", source="CORE")
            try:
                sectors = self.ingest_via_server()
                return f"Vault ingestion sequence completed ({sectors} sectors). Check terminals for chunk metrics."
            except Exception as e:
                return f"[SYSTEM FAULT] Ingestion failed: {e}"

        parts = clean_text.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd in self.command_router.command_registry:
            return self.command_router.route(cmd, args) if args else self.command_router.route(cmd)

        # /skills, /plugins, /<skill>: the extensions dir is on this machine,
        # so these resolve here; unknown /x falls through unchanged.
        prompt = None
        if clean_text.startswith("/"):
            from core_system.extensions import slash
            kind, value = slash.route(clean_text)
            if kind == "local":
                return value
            if kind == "prompt":
                prompt = value

        response = self._ask_ai_with_memory(clean_text, on_delta=on_delta, prompt=prompt,
                                            on_tool=on_tool, web=web, on_notice=on_notice,
                                            on_final=on_final)

        return response

    def _ask_ai_with_memory(self, user_text, on_delta=None, prompt=None, on_tool=None, web=False,
                            on_notice=None, on_final=None):
        """prompt: what the model sees when it differs from what the user typed
        (a /skill expansion); the ledger always keeps user_text. web: search
        the web for this one message. on_tool(name, status, error): streamed
        tool-call progress. on_notice(text): a server notice for this
        message (e.g. why a web search did not run). on_final(meta): the
        reply's {"reasoning", "cancelled"}."""
        self._ensure_active_session()

        self.chat_ledger.add_message(self.current_session_id, "user", user_text)
        self._autotitle_session(user_text)

        meta = {}

        def record_final(m):
            meta.update(m)
            if on_final is not None:
                on_final(m)

        # The server rebuilds history itself from the ledger by session_id (in
        # the model's own chat format); a client-side transcript used to be
        # built and sent here as "prompt" and was never read.
        response = self._send_to_server(
            query=prompt or user_text, session_id=self.current_session_id, on_delta=on_delta,
            on_tool=on_tool, web=web, on_notice=on_notice, on_final=record_final,
        )
        
        if "[SYSTEM ERROR]" not in response and "[HTTP ERROR]" not in response:
            # Persist ONLY the answer body, never the [ANALYSIS] scaffolding or
            # a <think> fragment. Stored turns are replayed verbatim as
            # assistant turns on the next request, so a stored empty or
            # degenerate turn teaches the model in-context that a blank reply
            # is the house style. That feedback loop is what produced the
            # self-sustaining run of empty responses on 2026-08-20.
            _analysis, body = parse_kernel_response(response)
            storable = is_storable_answer is None or is_storable_answer(body)
            if body and "[KERNEL FAULT]" not in body and storable:
                self._store_answer(body, meta.get("reasoning", ""))
            else:
                self.logger.warning(
                    "Empty or unstorable kernel body; turn not persisted to ledger.", source="CORE"
                )

        return response

    def _store_answer(self, body, reasoning=""):
        """Ledger write; the reasoning goes along only if this ledger accepts it."""
        add = self.chat_ledger.add_message
        try:
            takes_reasoning = "reasoning" in inspect.signature(add).parameters
        except (TypeError, ValueError):
            takes_reasoning = False
        if reasoning and takes_reasoning:
            add(self.current_session_id, "assistant", body, reasoning=reasoning)
        else:
            add(self.current_session_id, "assistant", body)

    def _autotitle_session(self, user_text):
        """Name a session after its first real prompt instead of 'New Session'."""
        session = self.chat_ledger.get_session(self.current_session_id)
        if not session or session.get("title") != "New Session":
            return
        title = " ".join(user_text.split())[:48].strip()
        if title:
            self.chat_ledger.update_session_title(self.current_session_id, title)

    def _ask_ai_isolated(self, prompt):
        return self._send_to_server(query=prompt)

    def _send_to_server(self, query, session_id=None, on_delta=None, on_tool=None, web=False,
                        on_notice=None, on_final=None):
        """POST the query; with on_delta, stream it via /ask/stream.

        on_delta(visible_text) is called with the answer text shown so far
        (reasoning and [ANALYSIS] scaffolding hidden), at most once per
        STREAM_EMIT_S. on_tool(name, status, error) is called for each tool
        event ("start", then "ok"/"error"). Either way the return value is
        the final formatted response, same as /ask's. A "notice" on the final
        reply goes to on_notice(text), never into the answer text; the
        reply's "reasoning" and "cancelled" fields go to on_final(meta).
        """
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {ACTIVE_API_KEY}"
            }

            payload = {"query": query}
            if session_id:
                payload["session_id"] = session_id
            if web:
                payload["web"] = True

            if on_delta is None:
                r = requests.post(AI_SERVER_URL, json=payload, headers=headers, timeout=900)
                r.raise_for_status()
                data = r.json()
                _notify(on_notice, data.get("notice"))
                _final(on_final, data)
                return data.get("response", "No response from brain.")

            r = requests.post(STREAM_URL, json=payload, headers=headers, timeout=900, stream=True)
            r.raise_for_status()
            raw = ""
            last_emit = 0.0
            dirty = False
            for line in r.iter_lines(decode_unicode=True):
                if not line:
                    continue
                event = json.loads(line)
                if "delta" in event:
                    raw += event["delta"]
                    dirty = True
                    now = time.monotonic()
                    if now - last_emit >= STREAM_EMIT_S:
                        last_emit, dirty = now, False
                        on_delta(stream_visible_body(raw))
                elif "tool" in event:
                    if dirty:  # show the text that led up to the call first
                        dirty = False
                        on_delta(stream_visible_body(raw))
                    if on_tool is not None:
                        on_tool(str(event["tool"]), str(event.get("status", "")), event.get("error"))
                elif event.get("done"):
                    _notify(on_notice, event.get("notice"))
                    status = event.get("status", 200)
                    if status >= 400:
                        return f"[HTTP ERROR] {status}: {event.get('error') or event.get('response', '')}"
                    _final(on_final, event)
                    return event.get("response", "No response from brain.")
            return "[SYSTEM ERROR] Stream ended without a final response."

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
        except Exception:
            pass

        sys.exit(0)