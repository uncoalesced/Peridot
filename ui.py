# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | INTERFACE & TELEMETRY OVERHAUL
# Copyright (C) 2026 uncoalesced
# 
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter import font as tkfont
import threading
import queue
import time
import psutil
import os
import ctypes
import requests
import re
import shutil
import subprocess
import webbrowser
import sys
from collections import deque
from pathlib import Path

import core as core_api  # module-level settings helpers; self.core is the instance
from config import (SERVER_HOST, SERVER_PORT, API_KEY, MODEL_PATH, TOTAL_VRAM_GB,
                    BASE_DIR, INPUT_PATH, MODEL_DIR, LOG_PATH, STORAGE_PATH)
from core_system import settings as local_settings
from core_system.extensions import registry
from core_system.providers import is_hf_model_dir
from core_system import modelfit
from core_system.security import MAX_INPUT_CHARS, is_file_safe

# --- UK ENGLISH DICTIONARY ENGINE ---
try:
    from spellchecker import SpellChecker
    SPELLCHECK_AVAILABLE = True
except ImportError:
    SPELLCHECK_AVAILABLE = False
    print("[WARN] pyspellchecker module missing. Run: pip install pyspellchecker")

# --- OS-LEVEL OVERRIDES ---
# Windows NT only: High DPI Awareness and Taskbar Icon
if sys.platform == "win32":
    try:
        # High DPI Awareness
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        # Taskbar Icon Separation
        myappid = 'uncoalesced.peridot.sovereign.1_5'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

# --- THEME & CONFIGURATION ---
# Every colour in this file comes from this block; tests/test_v160_ui_static.py
# fails on any #RRGGBB literal outside it.
# --- PALETTE ---
# PeridotDZN brand palette (official)
LIME = "#00FF19"
BLACK = "#000000"
GRAPE = "#5F5AA2"
MINT = "#EFF9F0"
TAUPE = "#A18276"
# Derived neutrals / status colours
SURFACE = "#0A0A0A"
SURFACE_2 = "#141414"
BORDER = "#1F1F1F"
MUTED = "#8A8A8A"       # de-emphasised text
GRAPE_TINT = "#8C87C9"  # grape lifted for legible text on black (raw grape is ~3.6:1)
RED = "#FF2A6D"
AMBER = "#FFD700"
ORANGE = "#FF8C00"
# --- END PALETTE ---

COLOR_BG = BLACK
COLOR_TEXT = MINT
COLOR_ACCENT = LIME
COLOR_DIM = SURFACE_2
COLOR_USER = GRAPE_TINT
COLOR_AI = MINT
COLOR_SYSTEM = TAUPE
COLOR_ERROR = RED
COLOR_INPUT = SURFACE
COLOR_CODE_BG = SURFACE

PAD = 8
PAD_S = 4
PAD_L = 16

# Named Tk fonts; the families are resolved against what is installed once a
# Tk root exists (_create_fonts). Widgets refer to them by name.
MONO_FAMILIES = ("Consolas", "Cascadia Mono", "DejaVu Sans Mono", "Courier New", "Courier")
UI_FAMILIES = (("Segoe UI",) if sys.platform == "win32" else ("DejaVu Sans",)) + (
    "DejaVu Sans", "Segoe UI", "Helvetica")
FONT_MAIN = "PeridotMain"      # chat messages
FONT_BOLD = "PeridotBold"      # user messages, telemetry values
FONT_CODE = "PeridotCode"      # code blocks, lists
FONT_SYSTEM = "PeridotSystem"  # >> system lines
FONT_UI = "PeridotUI"          # chrome: tabs, buttons, labels
FONT_BUTTON = "PeridotButton"
FONT_LINK = "PeridotLink"
FONT_SMALL = "PeridotSmall"
FONT_SMALL_MONO = "PeridotSmallMono"
FONT_LOGO = "PeridotLogo"
FONT_SPECS = {
    # name: (mono?, size, weight, slant, underline)
    FONT_MAIN: (False, 11, "normal", "roman", False),
    FONT_BOLD: (False, 11, "bold", "roman", False),
    FONT_CODE: (True, 11, "normal", "roman", False),
    FONT_SYSTEM: (True, 10, "normal", "roman", False),
    FONT_UI: (False, 9, "bold", "roman", False),
    FONT_BUTTON: (False, 10, "bold", "roman", False),
    FONT_LINK: (False, 9, "bold", "roman", True),
    FONT_SMALL: (False, 8, "normal", "italic", False),
    FONT_SMALL_MONO: (True, 8, "bold", "roman", False),
    FONT_LOGO: (True, 11, "bold", "roman", False),
}

ICON_PATH = Path(__file__).resolve().parent / "assets" / "logos" / "peridot.ico"


def _pick_family(candidates, available):
    """First installed family from candidates; Tk substitutes the last one."""
    return next((f for f in candidates if f in available), candidates[-1])


def _stream_suffix(displayed, new):
    """
    Diff the streamed text already on screen against the latest snapshot.

    ("append", suffix) when new only extends what is displayed; otherwise
    ("replace", new) -- e.g. nothing drawn yet, or the visible text shrank or
    was rewritten (the [ANALYSIS] header being stripped mid-stream).
    """
    if displayed is not None and new.startswith(displayed):
        return "append", new[len(displayed):]
    return "replace", new


# --- ATTACHMENTS / EXTENSIONS (pure helpers, no Tk) ---
ATTACH_MAX_CHARS = 20000
# core_system.security.sanitize_input refuses a whole message over this, so an
# attachment is cut to whatever still fits in the input box.
INPUT_MAX_CHARS = MAX_INPUT_CHARS
_ATTACH_READ_BYTES = 200_000  # > 4 bytes/char * ATTACH_MAX_CHARS
TEXT_EXTS = frozenset({
    ".txt", ".md", ".py", ".json", ".csv", ".log", ".yaml", ".yml", ".toml", ".ini",
    ".js", ".ts", ".html", ".css", ".c", ".cpp", ".h", ".rs", ".go", ".java"})


def format_attachment(name, text, limit=ATTACH_MAX_CHARS):
    """A file as a fenced block under a filename header, cut to limit chars."""
    limit = max(0, limit)
    note = ""
    if len(text) > limit:
        note = f"\n[truncated: showing the first {limit:,} characters]"
        text = text[:limit]
    fence = "````" if "```" in text else "```"
    lang = os.path.splitext(name)[1].lstrip(".").lower()
    return f"File: {name}\n{fence}{lang}\n{text.rstrip()}\n{fence}{note}\n"


def read_attachment(path):
    """Classify a picked file: ("pdf", None) | ("text", str) | ("unsupported", why)."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return "pdf", None
    with open(path, "rb") as f:
        data = f.read(_ATTACH_READ_BYTES + 1)
    if ext in TEXT_EXTS:
        text = data[:_ATTACH_READ_BYTES].decode("utf-8", errors="replace")
        return "text", text.replace("\r\n", "\n")
    if len(data) <= _ATTACH_READ_BYTES and b"\x00" not in data:
        try:
            return "text", data.decode("utf-8").replace("\r\n", "\n")
        except UnicodeDecodeError:
            pass
    return "unsupported", (f"{os.path.basename(path)}: this file type is not supported yet "
                           "(PDFs and text files only; images arrive with multimodal support).")


def plugin_status(name, current_hash, approved):
    """'Approved' | 'Changed since approval' | 'Needs approval'."""
    pinned = (approved or {}).get(name)
    if pinned is None:
        return "Needs approval"
    return "Approved" if pinned == current_hash else "Changed since approval"


def perm_summary(perms):
    return (f"network: {'yes' if perms.get('network') else 'no'}, "
            f"files: {perms.get('files', 'none')}")


def venv_python(base_dir):
    """The project venv's interpreter if it exists, else the running one."""
    sub = ("Scripts", "python.exe") if sys.platform == "win32" else ("bin", "python")
    candidate = Path(base_dir, "venv", *sub)
    return str(candidate) if candidate.is_file() else sys.executable


def mcp_setup_command(base_dir, python):
    script = Path(base_dir) / "mcp" / "peridot_mcp.py"
    return f'claude mcp add peridot -- "{python}" "{script}"'

SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}


# --- MESSAGE QUEUE (pure, no Tk) ---
class MessageQueue:
    """Prompts sent while a reply is in flight; they go out in order after it."""

    def __init__(self):
        self._items = []
        self._seq = 0

    def enqueue(self, text, web=False):
        self._seq += 1
        self._items.append({"id": self._seq, "text": text, "web": bool(web)})
        return self._seq

    def cancel(self, qid):
        before = len(self._items)
        self._items = [i for i in self._items if i["id"] != qid]
        return len(self._items) != before

    def pop_next(self):
        return self._items.pop(0) if self._items else None

    def items(self):
        return list(self._items)

    def __len__(self):
        return len(self._items)


def queue_preview(text, limit=40):
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[:limit].rstrip() + "…"


# --- MODEL SWAP (pure, no Tk) ---
# Fit heuristic. The real KV cache at ctx 8192 is 2 bytes * 8192 * n_layers *
# kv_width, but n_layers is not known without parsing the GGUF header, so it
# is approximated as 10% of the file size, plus ~0.5 GB of CUDA/runtime
# overhead. "partial offload" = at least half of that need fits in VRAM.
# ponytail: size heuristic; read n_layer/n_embd from the GGUF header if it misrates models.
KV_FRACTION = 0.10
RUNTIME_OVERHEAD_GB = 0.5
SERVER_PID_FILE = STORAGE_PATH / "server.pid"  # read by launcher.kill_pidfile_server


def model_fit(size_gb, vram_gb):
    need = size_gb * (1 + KV_FRACTION) + RUNTIME_OVERHEAD_GB
    if vram_gb > 0 and need <= vram_gb:
        return "fits in VRAM"
    if vram_gb > 0 and need <= vram_gb * 2:
        return "partial offload"
    return "CPU-heavy"


def model_choices(model_dir, vram_gb):
    """[(label, name)] for each .gguf file and HF safetensors folder in model_dir."""
    try:
        files = sorted(p for p in Path(model_dir).iterdir()
                       if (p.is_file() and p.suffix.lower() == ".gguf") or is_hf_model_dir(p))
    except OSError:
        return []
    out = []
    for p in files:
        size = sum(f.stat().st_size for f in p.glob("*.safetensors")) if p.is_dir() else p.stat().st_size
        gb = size / 1024 ** 3
        out.append((f"{p.name}  ·  {gb:.1f} GB  ·  {model_fit(gb, vram_gb)}", p.name))
    return out


def tail_lines(path, n=10):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return "".join(deque(f, n)).rstrip()
    except OSError:
        return ""


def run_model_swap(name, post, spawn, health, sleep, on_status=lambda s: None,
                   stop_timeout=15, load_timeout=240):
    """Persist name as the active model, restart the engine on it, wait for it.

    post(path, body) -> dict, {"error": ...} on failure. health() -> None when
    nothing answers, else (status_code, json dict). spawn() -> a Popen-like
    with poll(). Returns ("ok", loaded model) | ("rejected", why) | ("failed", why).
    """
    result = post("/settings", {"model.active": name})
    if "error" in result:
        return "rejected", str(result["error"])
    post("/shutdown", None)  # the engine exits; a dropped connection is expected
    waited = 0
    while health() is not None:
        if waited >= stop_timeout:
            return "failed", f"the old engine still answered /health after {stop_timeout}s"
        sleep(1)
        waited += 1
    proc = spawn()
    for waited in range(1, load_timeout + 1):
        sleep(1)
        on_status(f"Loading {name}… {waited}s")
        code = proc.poll()
        if code is not None:
            return "failed", f"the engine exited during boot (code {code})"
        h = health()
        if h is not None and h[0] == 200:
            return "ok", h[1].get("model") or name
    return "failed", f"the engine did not come up within {load_timeout}s"


def _engine_post(path, body=None):
    """POST to the engine. {"error": str} on any failure; never raises."""
    try:
        r = requests.post(SERVER_URL + path, json=body, headers=HEADERS, timeout=10)
        data = r.json()
    except (requests.exceptions.RequestException, ValueError) as e:
        return {"error": str(e)}
    data = data if isinstance(data, dict) else {}
    if r.status_code != 200:
        return {"error": str(data.get("error") or f"HTTP {r.status_code}")}
    return data


def _health_probe():
    """None when the engine does not answer, else (status_code, json dict)."""
    try:
        r = requests.get(SERVER_URL + "/health", timeout=2)
    except requests.exceptions.RequestException:
        return None
    try:
        data = r.json()
    except ValueError:
        data = None
    return r.status_code, data if isinstance(data, dict) else {}


def spawn_server(model):
    """Start server.py with this interpreter, no console window, logging to
    logs/server.log; its pid goes to storage/server.pid for launcher cleanup."""
    # ACTIVE_MODEL_NAME may be in this process's env from the launcher's .env load.
    env = dict(os.environ, ACTIVE_MODEL_NAME=model)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    LOG_PATH.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH / "server.log", "a") as log:  # the child keeps its own handle
        proc = subprocess.Popen([sys.executable, "server.py"], cwd=str(BASE_DIR), stdout=log,
                                stderr=subprocess.STDOUT, env=env, creationflags=flags)
    SERVER_PID_FILE.write_text(str(proc.pid))
    return proc

# --- ASCII LOGO ---
ASCII_LOGO = """
██████╗ ███████╗██████╗ ██╗██████╗  ██████╗ ████████╗
██╔══██╗██╔════╝██╔══██╗██║██╔══██╗██╔═══██╗╚══██╔══╝
██████╔╝█████╗  ██████╔╝██║██║  ██║██║   ██║   ██║   
██╔═══╝ ██╔══╝  ██╔══██╗██║██║  ██║██║   ██║   ██║   
██║     ███████╗██║  ██║██║██████╔╝╚██████╔╝   ██║   
╚═╝     ╚══════╝╚═╝  ╚═╝╚═╝╚═════╝  ╚═════╝    ╚═╝   
"""
VERSION_TEXT = "SOVEREIGN KERNEL v1.6.1-beta [AGENTIC]\nENGINEERED BY UNCOALESCED"


class TechProgressBar(tk.Canvas):
    def __init__(self, parent, width=100, height=18, bg=COLOR_DIM):
        super().__init__(
            parent, width=width, height=height, bg=bg, highlightthickness=0
        )
        self.w, self.h = width, height
        self.rect = self.create_rectangle(0, 0, 0, height, fill=COLOR_ACCENT, width=0)
        self.text_shadow = self.create_text(
            width / 2 + 1, height / 2 + 1, text="0%", fill=BLACK, font=FONT_SMALL_MONO
        )
        self.text_main = self.create_text(
            width / 2, height / 2, text="0%", fill=MINT, font=FONT_SMALL_MONO
        )

    def update_value(self, percent):
        percent = max(0, min(100, percent))
        col = (
            LIME if percent <= 60
            else (AMBER if percent <= 85 else ORANGE if percent <= 95 else RED)
        )
        self.coords(self.rect, 0, 0, (percent / 100) * self.w, self.h)
        self.itemconfig(self.rect, fill=col)
        self.itemconfig(self.text_shadow, text=f"{int(percent)}%")
        self.itemconfig(self.text_main, text=f"{int(percent)}%")
        self.tag_raise(self.text_shadow)
        self.tag_raise(self.text_main)


class PeridotUI:
    def __init__(self, core):
        self.core = core
        self.root = tk.Tk()
        self.is_processing = False
        self.research_active = False
        self._nvml_handle = None  # set by the telemetry worker; False = no GPU
        # Mirrors of server settings (GET/POST /settings is the only source).
        self.web_enabled = False
        self.web_armed = False  # per-message web search, cleared on send
        self._allow_folders = []
        self._ext_snapshot = None  # last _extensions_snapshot(), Tk thread only
        self._queue = MessageQueue()  # prompts sent while busy, see handle_input
        self._swapping = False  # a model swap is restarting the engine
        self._listening = False  # a voice capture is running
        self._btn_styles = {}  # str(button) -> idle/hover colours, see _style_button

        # Session State
        self.sessions = []
        self._current_session_menu_index = None

        # Kinetic Scroll State Variables
        self.chat_scroll_velocity = 0.0
        self.chat_scroll_animating = False

        # Worker threads never touch Tk: they enqueue callables via ui_call()
        # and _pump_ui_queue runs them on the main thread.
        self._ui_queue = queue.Queue()
        self._stream_state = None
        self._entry_height = 1

        # Loaded off-thread after the window is up (_load_spellchecker); until
        # then spellcheck is simply skipped.
        self.spell = None

        self._create_fonts()
        self._setup_main_window()
        self._configure_notebook_styles()
        self._load_icons()
        self._create_widgets()
        self._configure_styles()
        self._bind_shortcuts()
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _create_fonts(self):
        available = set(tkfont.families(self.root))
        mono = _pick_family(MONO_FAMILIES, available)
        ui = _pick_family(UI_FAMILIES, available)
        # Held on self: a tkfont.Font deletes its Tk font when collected.
        self._fonts = {
            name: tkfont.Font(root=self.root, name=name, family=mono if is_mono else ui,
                              size=size, weight=weight, slant=slant, underline=underline)
            for name, (is_mono, size, weight, slant, underline) in FONT_SPECS.items()
        }

    def _setup_main_window(self):
        self.root.title("Peridot | Sovereign OS")
        self.root.geometry("1150x800")
        self.root.configure(bg=COLOR_BG)
        # Defaults for every tk.Button: flat, palette-coloured press state
        # instead of the native grey flash.
        self.root.option_add("*Button.relief", "flat")
        self.root.option_add("*Button.borderWidth", 0)
        self.root.option_add("*Button.activeBackground", BORDER)
        self.root.option_add("*Button.activeForeground", LIME)
        self.root.option_add("*Button.cursor", "hand2")
        self.root.option_add("*Menu.background", SURFACE_2)
        self.root.option_add("*Menu.foreground", MINT)
        self.root.option_add("*Menu.activeBackground", LIME)
        self.root.option_add("*Menu.activeForeground", BLACK)
        self.root.option_add("*Menu.font", FONT_UI)

        # Windows NT only: Icon loading via win32 APIs
        if sys.platform == "win32":
            try:
                icon_path = ICON_PATH
                self.root.iconbitmap(str(icon_path))

                hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
                if hwnd:
                    hicon = ctypes.windll.user32.LoadImageW(0, str(icon_path), 1, 0, 0, 0x00000010 | 0x00000020)
                    ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, hicon)
                    ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, hicon)
            except Exception:
                pass

            try:
                hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(2)), 4)
            except Exception:
                pass

    def _load_icons(self):
        """
        Load the button glyphs, falling back to a text label per icon.

        This pointed at assets/ui/icons/{mic,execute,settings,vault}.png, a
        directory that has never existed in the tree -- the shipped icons are
        .ico files under assets/icons/ with different names. The exists()
        guard swallowed it, so every button silently rendered its text
        fallback and the image branch below had never once executed.
        Icons must be pre-sized 16x16 PNGs: tk.PhotoImage cannot read .ico
        or resample (Pillow was dropped in v1.6.1).

        The MIC/SEND buttons are text-only: their .ico glyphs are non-square
        and were squashed into 16x16. "settings" and "vault" keep their text
        labels deliberately, rather than naming files that are not there.
        """
        self.icons = {}
        base_dir = Path(__file__).parent.resolve() / "assets" / "icons"
        icons_to_load = {
            "settings": ("[SET]", None),
            "vault": ("[DIR]", None),
        }
        for key, (fallback, filename) in icons_to_load.items():
            if filename is None:
                self.icons[key] = fallback
                continue
            icon_path = base_dir / filename
            try:
                if icon_path.exists():
                    self.icons[key] = tk.PhotoImage(file=str(icon_path))
                else:
                    self.icons[key] = fallback
            except Exception:
                self.icons[key] = fallback

    def _configure_notebook_styles(self):
        """Injects custom terminal aesthetics into the tab engine and Comboboxes."""
        style = ttk.Style()
        style.theme_use("clam")
        
        # Notebook Tab Styling (Overriding light/dark colors kills the white outline)
        style.configure("TNotebook", background=COLOR_BG, borderwidth=0, lightcolor=COLOR_BG, darkcolor=COLOR_BG,
                        bordercolor=BORDER, tabmargins=[0, 0, 0, 0])
        style.configure("TNotebook.Tab", background=SURFACE, foreground=MUTED, font=FONT_UI,
                        padding=[PAD_L, PAD_S + 2], borderwidth=0, lightcolor=SURFACE, darkcolor=SURFACE,
                        bordercolor=BORDER, focuscolor=SURFACE_2)
        style.map("TNotebook.Tab",
                  background=[("selected", SURFACE_2), ("active", SURFACE_2)],
                  foreground=[("selected", LIME), ("active", MINT)])

        # Modern Deep-Theme Combobox Styling
        style.configure("TCombobox",
            fieldbackground=SURFACE,
            background=SURFACE_2,
            foreground=MINT,
            bordercolor=BORDER,
            arrowcolor=MUTED,
            darkcolor=SURFACE_2,
            lightcolor=SURFACE_2,
            padding=PAD_S,
        )
        style.map("TCombobox",
            fieldbackground=[("readonly", SURFACE)],
            selectbackground=[("readonly", SURFACE)],
            selectforeground=[("readonly", MINT)],
            bordercolor=[("focus", LIME), ("hover", BORDER)],
            arrowcolor=[("hover", LIME), ("pressed", LIME)],
        )

        # Dropdown Popup List Styling
        self.root.option_add('*TCombobox*Listbox.background', SURFACE)
        self.root.option_add('*TCombobox*Listbox.foreground', MINT)
        self.root.option_add('*TCombobox*Listbox.selectBackground', SURFACE_2)
        self.root.option_add('*TCombobox*Listbox.selectForeground', LIME)
        self.root.option_add('*TCombobox*Listbox.font', FONT_CODE)

        # Thin, arrowless dark scrollbar (rejects native Win32 white artifacts
        # entirely); the thumb lights lime on hover/drag.
        style.layout("Vertical.TScrollbar", [
            ("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
                ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
        style.configure("Vertical.TScrollbar",
            background=BORDER,
            troughcolor=COLOR_BG,
            bordercolor=COLOR_BG,
            lightcolor=BORDER,
            darkcolor=BORDER,
            arrowsize=PAD,
            gripcount=0
        )
        style.map("Vertical.TScrollbar",
            background=[("pressed", LIME), ("active", LIME)],
            lightcolor=[("pressed", LIME), ("active", LIME)],
            darkcolor=[("pressed", LIME), ("active", LIME)],
        )

        # Extensions tables
        style.configure("Treeview", background=SURFACE, fieldbackground=SURFACE, foreground=MINT,
                        font=FONT_CODE, bordercolor=BORDER, lightcolor=SURFACE, darkcolor=SURFACE,
                        rowheight=self._fonts[FONT_CODE].metrics("linespace") + PAD_S * 2)
        style.map("Treeview", background=[("selected", SURFACE_2)], foreground=[("selected", LIME)])
        style.configure("Treeview.Heading", background=SURFACE_2, foreground=MUTED, font=FONT_UI,
                        bordercolor=BORDER, lightcolor=SURFACE_2, darkcolor=SURFACE_2, relief="flat")
        style.map("Treeview.Heading", background=[("active", BORDER)], foreground=[("active", MINT)])

    def _create_widgets(self):
        # Search Bar Overlay (Hidden by default)
        self.search_frame = tk.Frame(self.root, bg=SURFACE_2)
        self.search_entry = tk.Entry(self.search_frame, bg=SURFACE, fg=MINT, font=FONT_MAIN, insertbackground=LIME,
                                     relief=tk.FLAT, highlightthickness=1, highlightcolor=LIME,
                                     highlightbackground=BORDER)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=PAD_L, pady=PAD, ipady=PAD_S)
        self.search_entry.bind("<KeyRelease>", self._execute_search)
        self.search_entry.bind("<Return>", self._execute_search)
        self.search_entry.bind("<Escape>", self._close_search)
        btn_close_search = tk.Button(self.search_frame, text="[X]", bg=SURFACE_2, fg=COLOR_ERROR, font=FONT_UI,
                                     command=self._close_search, padx=PAD, pady=PAD_S)
        btn_close_search.pack(side=tk.RIGHT, padx=(0, PAD_L))

        # Notebook Layout Manager Partition
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=PAD_L, pady=(PAD_L, PAD))

        # Tab 1: Chat Buffer Matrix (PanedWindow with session sidebar)
        self.tab_chat = tk.Frame(self.notebook, bg=COLOR_BG)
        self.notebook.add(self.tab_chat, text="[01] CHAT MATRIX")

        # Toggle button row above chat pane
        self.chat_toolbar = tk.Frame(self.tab_chat, bg=COLOR_BG)
        self.chat_toolbar.pack(fill=tk.X, pady=(PAD, 0))

        self.btn_toggle_sessions = tk.Button(self.chat_toolbar, text="[>] SESSIONS",
                                              bg=SURFACE_2, fg=MUTED, font=FONT_UI,
                                              padx=PAD, pady=PAD_S,
                                              command=self._toggle_session_drawer)
        self.btn_toggle_sessions.pack(side=tk.LEFT)

        # Re-enforced resizable PanedWindow
        self.chat_pane = tk.PanedWindow(self.tab_chat, orient=tk.HORIZONTAL,
                                         sashrelief=tk.FLAT, sashwidth=PAD_S, sashcursor="sb_h_double_arrow",
                                         bg=BORDER, bd=0)
        self.chat_pane.pack(fill=tk.BOTH, expand=True, pady=(PAD, 0))

        # Left pane: Session sidebar (hidden by default, managed via toggle)
        self.session_frame = tk.Frame(self.chat_pane, bg=SURFACE, width=250)
        self.session_header = tk.Label(self.session_frame, text="SESSIONS",
                                        bg=SURFACE, fg=MUTED, font=FONT_UI, anchor="w")
        self.session_header.pack(fill=tk.X, padx=PAD, pady=(PAD, PAD_S))

        self.btn_new_session = tk.Button(self.session_frame, text="[+] NEW SESSION",
                                          bg=SURFACE_2, fg=MINT, font=FONT_UI, pady=PAD_S,
                                          command=self._new_session)
        self.btn_new_session.pack(fill=tk.X, padx=PAD, pady=(0, PAD))

        session_scroll_frame = tk.Frame(self.session_frame, bg=SURFACE)
        session_scroll_frame.pack(fill=tk.BOTH, expand=True, padx=PAD, pady=(0, PAD))

        self.session_listbox = tk.Listbox(
            session_scroll_frame, bg=SURFACE, fg=MINT,
            font=FONT_MAIN, relief=tk.FLAT, highlightthickness=0, bd=0,
            selectbackground=SURFACE_2, selectforeground=LIME,
            activestyle="none"
        )
        self.session_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Apply the dark ttk scrollbar style to the sidebar
        session_scroll = ttk.Scrollbar(session_scroll_frame, orient=tk.VERTICAL,
                                       command=self.session_listbox.yview,
                                       style="Vertical.TScrollbar")
        session_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.session_listbox.config(yscrollcommand=session_scroll.set)

        self.session_listbox.bind("<ButtonRelease-1>", self._on_session_select)

        # Right-click context menu for session delete and rename
        self.session_menu = tk.Menu(self.tab_chat, tearoff=0)  # colours: *Menu option defaults
        self.session_menu.add_command(label="Rename Session", command=self._rename_session)
        self.session_menu.add_command(label="Delete Session", command=self._delete_session)
        self.session_listbox.bind("<Button-3>", self._show_session_menu)

        self.session_drawer_open = False

        # --- RIGHT PANE: CUSTOM CHAT WIDGET ---
        # Replacing the legacy 'scrolledtext' module to eradicate the white scrollbar artifact
        self.chat_frame = tk.Frame(self.chat_pane, bg=COLOR_BG, bd=0, highlightthickness=0)
        
        self.chat = tk.Text(
            self.chat_frame, wrap=tk.WORD, bg=COLOR_BG, fg=COLOR_TEXT,
            font=FONT_MAIN, insertbackground=COLOR_ACCENT, bd=0,
            highlightthickness=0, padx=PAD_L, pady=PAD, state=tk.DISABLED,
            selectbackground=GRAPE, selectforeground=MINT, inactiveselectbackground=GRAPE,
        )
        self.chat.bind("<MouseWheel>", self._on_kinetic_scroll)

        # Build our custom dark scrollbar and link it to the text widget
        self.chat_scroll = ttk.Scrollbar(self.chat_frame, orient=tk.VERTICAL, command=self.chat.yview, style="Vertical.TScrollbar")
        self.chat.config(yscrollcommand=self.chat_scroll.set)
        
        # Pack the custom bar to the right, and the text area to the left
        self.chat_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Add the entire custom frame to the pane (hiding the drawer by default)
        self.chat_pane.add(self.chat_frame, minsize=400)

        # Tab 2: Secured Document Storage Matrix
        self.tab_vault = tk.Frame(self.notebook, bg=COLOR_BG)
        vault_kw = {"image": self.icons["vault"], "compound": tk.LEFT, "text": " KERNEL VAULT"} if isinstance(self.icons.get("vault"), tk.PhotoImage) else {"text": f"{self.icons.get('vault', '[DIR]')} KERNEL VAULT"}
        self.notebook.add(self.tab_vault, **vault_kw)

        self.vault_label = tk.Label(self.tab_vault, text=">> DATA-INGEST SECURE CONSOLE VECTOR DIRECTORY:", bg=COLOR_BG, fg=MUTED, font=FONT_UI, anchor="w")
        self.vault_label.pack(fill=tk.X, padx=PAD_L, pady=(PAD_L, PAD))

        self.vault_list = tk.Listbox(
            self.tab_vault, bg=SURFACE, fg=MINT, font=FONT_CODE, bd=0,
            relief=tk.FLAT, highlightthickness=1, highlightcolor=BORDER, highlightbackground=BORDER,
            selectbackground=SURFACE_2, selectforeground=LIME, activestyle="none"
        )
        self.vault_list.pack(fill=tk.BOTH, expand=True, padx=PAD_L, pady=(0, PAD_L))

        # Tab 3: Skills & Plugins
        self.tab_extensions = tk.Frame(self.notebook, bg=COLOR_BG)
        self.notebook.add(self.tab_extensions, text="[EXT] EXTENSIONS")
        self._build_extensions_tab()

        # Tab 4: Settings & Hardware Configuration
        self.tab_settings = tk.Frame(self.notebook, bg=COLOR_BG)
        set_kw = {"image": self.icons["settings"], "compound": tk.LEFT, "text": " SETTINGS"} if isinstance(self.icons.get("settings"), tk.PhotoImage) else {"text": f"{self.icons.get('settings', '[SET]')} SETTINGS"}
        self.notebook.add(self.tab_settings, **set_kw)
        self._build_settings_tab()

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # Responsive Input Controls Layout
        # Input row and status bar are packed *before* the notebook so that
        # when the window is short the chat shrinks, not the controls (pack
        # clips whatever was packed last).
        self.in_frame = tk.Frame(self.root, bg=COLOR_BG)
        self.in_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=PAD_L, pady=(0, PAD_L), before=self.notebook)
        tk.Frame(self.in_frame, bg=BORDER, height=1).grid(row=0, column=0, columnspan=5, sticky="ew", pady=(0, PAD))

        self.in_frame.columnconfigure(0, weight=1)

        # Prompts sent while a reply streams wait here as chips (_render_queue).
        self.queue_strip = tk.Frame(self.in_frame, bg=COLOR_BG)
        self.queue_strip.grid(row=1, column=0, columnspan=5, sticky="ew", pady=(0, PAD_S))
        self.queue_strip.grid_remove()

        # The lime focus ring is the input's only accent.
        self.entry = tk.Text(
            self.in_frame, bg=COLOR_INPUT, fg=MINT, font=FONT_MAIN,
            insertbackground=COLOR_ACCENT, relief=tk.FLAT, bd=0, padx=PAD, pady=PAD,
            highlightthickness=1, highlightcolor=LIME, highlightbackground=BORDER,
            selectbackground=GRAPE, selectforeground=MINT,
            height=1, width=1, wrap=tk.WORD, undo=False, spacing2=2
        )
        self.entry.grid(row=2, column=0, sticky="nsew")

        self.entry.bind("<Return>", self._on_enter)
        self.entry.bind("<Shift-Return>", self._on_shift_enter)
        self.entry.bind("<KeyRelease>", self._on_key_release)
        self.entry.bind("<Button-3>", self._show_spellcheck_menu)

        # entry | ATTACH | SEARCH | MIC | SEND, one builder so all four share
        # font, padding, 1px border and hover behaviour.
        self.btn_attach = self._input_button("ATTACH", self._attach_files, column=1)
        # Arms web search for the next message only (see handle_input).
        self.btn_search = self._input_button("[ ] SEARCH", self._toggle_web_armed, column=2)
        self.btn_mic = self._input_button("MIC", self.handle_voice, column=3)
        self.btn_send = self._input_button("SEND", self.handle_input, column=4)
        self._set_send_mode(False)
        self._set_web_armed(False)

        # Fixed Status Telemetry Panel
        self.stat_bar = tk.Frame(self.root, bg=SURFACE, highlightthickness=0)
        self.stat_bar.pack(fill=tk.X, side=tk.BOTTOM, before=self.in_frame)
        tk.Frame(self.stat_bar, bg=BORDER, height=1).pack(fill=tk.X, side=tk.TOP)

        self.lbl_status = tk.Label(self.stat_bar, text="FSM: CONNECTING", bg=SURFACE, fg=MUTED, font=FONT_UI)
        self.lbl_status.pack(side=tk.LEFT, padx=(PAD_L, PAD), pady=PAD)

        self.btn_research = tk.Button(
            self.stat_bar, text="RESEARCH: OFF", bg=SURFACE_2, fg=MINT, font=FONT_UI,
            padx=PAD, pady=2, command=self._toggle_research
        )
        self.btn_research.pack(side=tk.LEFT, padx=PAD)

        self.btn_web = tk.Button(
            self.stat_bar, text="WEB: OFF", bg=SURFACE_2, fg=MUTED, font=FONT_UI,
            padx=PAD, pady=2, command=self._toggle_web
        )
        self.btn_web.pack(side=tk.LEFT, padx=(0, PAD))

        for m in [("RAM", "bar_ram"), ("CPU", "bar_cpu"), ("VRAM", "bar_vram")]:
            self._add_monitor(m[0], m[1])

    def _build_settings_tab(self):
        """Constructs hardware-aware configuration matrix."""
        # Top Config Container
        config_frame = tk.Frame(self.tab_settings, bg=COLOR_BG)
        config_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(PAD_L * 2, PAD_L), pady=PAD_L)
        extras_frame = tk.Frame(self.tab_settings, bg=COLOR_BG)
        extras_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(PAD_L, PAD_L * 2), pady=PAD_L)
        self._build_settings_extras(extras_frame)

        tk.Label(config_frame, text=">> CURRENT ACTIVE MODEL:", bg=COLOR_BG, fg=MUTED, font=FONT_UI, anchor="w").pack(fill=tk.X, pady=(0, PAD))

        # Filled from the engine's /health at startup and after a swap.
        self.lbl_current_model = tk.Label(config_frame, text="   (asking the engine...)", bg=COLOR_BG, fg=COLOR_TEXT, font=FONT_MAIN, anchor="w")
        self.lbl_current_model.pack(fill=tk.X, pady=(0, PAD_L))

        tk.Label(config_frame, text=">> HARDWARE-AWARE MODEL SWAP (models/):", bg=COLOR_BG, fg=MUTED, font=FONT_UI, anchor="w").pack(fill=tk.X, pady=(0, PAD))

        self.model_var = tk.StringVar()
        self.model_dropdown = ttk.Combobox(
            config_frame, textvariable=self.model_var, state="readonly", font=FONT_CODE
        )
        self.model_dropdown.pack(fill=tk.X, pady=(0, PAD))

        # The Combobox popdown is a separate override-redirect toplevel; on
        # Windows it survives an Alt-Tab and floats over whatever app you
        # switch to. Tk owns that window, so close it from the root's own
        # focus-out rather than trying to reach into the widget.
        self.root.bind("<FocusOut>", self._close_dropdown_popdown, add="+")

        self._populate_models()

        self.btn_swap = tk.Button(
            config_frame, text="APPLY WEIGHTS AND REBOOT KERNEL", bg=COLOR_DIM, fg=COLOR_TEXT,
            disabledforeground=MUTED, font=FONT_UI, padx=PAD_L, pady=PAD_S + 2,
            command=self._swap_model
        )
        self.btn_swap.pack(anchor="w", pady=(0, PAD_L))

        tk.Frame(config_frame, bg=BORDER, height=1).pack(fill=tk.X, pady=(0, PAD_L))
        self._build_get_models(config_frame)
        tk.Frame(config_frame, bg=BORDER, height=1).pack(fill=tk.X, pady=(0, PAD_L))

        tk.Label(config_frame, text=">> HARDWARE MEMORY MANAGEMENT:", bg=COLOR_BG, fg=MUTED, font=FONT_UI, anchor="w").pack(fill=tk.X, pady=(0, PAD))

        btn_reclaim = tk.Button(
            config_frame, text="FORCE-RECLAIM VRAM", bg=COLOR_DIM, fg=COLOR_ERROR,
            font=FONT_UI, padx=PAD_L, pady=PAD_S + 2, command=self._force_reclaim_vram
        )
        btn_reclaim.pack(anchor="w", pady=(0, PAD_L))

        # KERNEL TELEMETRY DASHBOARD
        tk.Frame(config_frame, bg=BORDER, height=1).pack(fill=tk.X, pady=(0, PAD_L))

        tk.Label(config_frame, text=">> KERNEL TELEMETRY DASHBOARD:", bg=COLOR_BG, fg=MUTED, font=FONT_UI, anchor="w").pack(fill=tk.X, pady=(0, PAD))

        # Telemetry metrics frame
        telemetry_frame = tk.Frame(config_frame, bg=COLOR_BG)
        telemetry_frame.pack(fill=tk.X, pady=(0, PAD))

        # FSM State
        fsm_frame = tk.Frame(telemetry_frame, bg=COLOR_BG)
        fsm_frame.pack(fill=tk.X, pady=2)
        tk.Label(fsm_frame, text="FSM State:", bg=COLOR_BG, fg=MUTED, font=FONT_UI, anchor="w", width=20).pack(side=tk.LEFT)
        self.lbl_fsm_state = tk.Label(fsm_frame, text="BOOTING...", bg=COLOR_BG, fg=COLOR_ACCENT, font=FONT_BOLD, anchor="w")
        self.lbl_fsm_state.pack(side=tk.LEFT, padx=(PAD, 0))

        # System Health Score
        health_frame = tk.Frame(telemetry_frame, bg=COLOR_BG)
        health_frame.pack(fill=tk.X, pady=2)
        tk.Label(health_frame, text="System Health:", bg=COLOR_BG, fg=MUTED, font=FONT_UI, anchor="w", width=20).pack(side=tk.LEFT)
        self.lbl_health_score = tk.Label(health_frame, text="0%", bg=COLOR_BG, fg=COLOR_TEXT, font=FONT_BOLD, anchor="w")
        self.lbl_health_score.pack(side=tk.LEFT, padx=(PAD, 0))

        # Average Handoff Latency
        latency_frame = tk.Frame(telemetry_frame, bg=COLOR_BG)
        latency_frame.pack(fill=tk.X, pady=2)
        tk.Label(latency_frame, text="Avg Handoff Latency:", bg=COLOR_BG, fg=MUTED, font=FONT_UI, anchor="w", width=20).pack(side=tk.LEFT)
        self.lbl_avg_latency = tk.Label(latency_frame, text="0ms", bg=COLOR_BG, fg=COLOR_TEXT, font=FONT_BOLD, anchor="w")
        self.lbl_avg_latency.pack(side=tk.LEFT, padx=(PAD, 0))

        # Kernel Panic Count
        panic_frame = tk.Frame(telemetry_frame, bg=COLOR_BG)
        panic_frame.pack(fill=tk.X, pady=2)
        tk.Label(panic_frame, text="Kernel Panics:", bg=COLOR_BG, fg=MUTED, font=FONT_UI, anchor="w", width=20).pack(side=tk.LEFT)
        self.lbl_panic_count = tk.Label(panic_frame, text="0", bg=COLOR_BG, fg=COLOR_TEXT, font=FONT_BOLD, anchor="w")
        self.lbl_panic_count.pack(side=tk.LEFT, padx=(PAD, 0))

        # Footer Navigation Links
        footer_frame = tk.Frame(self.tab_settings, bg=COLOR_BG)
        # Packed ahead of the two columns so it spans the full width.
        footer_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=PAD_L * 2, pady=PAD_L, before=config_frame)
        tk.Frame(footer_frame, bg=BORDER, height=1).pack(fill=tk.X, pady=(0, PAD))

        link_frame = tk.Frame(footer_frame, bg=COLOR_BG)
        link_frame.pack(anchor="center")

        links = [
            ("Report Bugs", "https://github.com/uncoalesced/Peridot/issues"),
            ("About Peridot", "https://github.com/uncoalesced/Peridot/wiki/The-Sovereign-Directive"),
            ("Contribute", "https://github.com/uncoalesced/Peridot/blob/main/CONTRIBUTING.md")
        ]

        for text, url in links:
            lbl = tk.Label(link_frame, text=f"[{text}]", bg=COLOR_BG, fg=COLOR_USER, font=FONT_LINK, cursor="hand2")
            lbl.pack(side=tk.LEFT, padx=PAD_L)
            lbl.bind("<Button-1>", lambda e, u=url: webbrowser.open_new(u))

    def _close_dropdown_popdown(self, event=None):
        """Withdraw any open Combobox popdown when the app loses focus."""
        if event is not None and event.widget is not self.root:
            return
        try:
            popdown = self.root.tk.call("ttk::combobox::PopdownWindow", self.model_dropdown)
            self.root.tk.call("wm", "withdraw", popdown)
        except Exception:
            pass

    def _populate_models(self):
        """Fill the swap dropdown from MODEL_DIR (.gguf + HF folders), rated against total VRAM."""
        choices = model_choices(MODEL_DIR, TOTAL_VRAM_GB)
        self.available_models_map = dict(choices)
        self.model_dropdown["values"] = ([label for label, _ in choices]
                                         or [" [ERROR] no models in models/ - use GET MODELS."])
        self.model_dropdown.current(0)

    # --- GET MODELS (core_system.modelfit: hardware check, top 3, any HF repo, download) ---
    def _build_get_models(self, parent):
        tk.Label(parent, text=">> GET MODELS (checked against this machine, saved to models/):", bg=COLOR_BG,
                 fg=MUTED, font=FONT_UI, anchor="w").pack(fill=tk.X, pady=(0, PAD))
        self.lbl_fit_hw = tk.Label(parent, text="   FIND TOP 3 scans this machine and asks Hugging Face.",
                                   bg=COLOR_BG, fg=COLOR_TEXT, font=FONT_CODE, anchor="w", justify=tk.LEFT)
        self.lbl_fit_hw.pack(fill=tk.X, pady=(0, PAD))
        self.fit_list = tk.Listbox(parent, height=5, bg=COLOR_DIM, fg=COLOR_TEXT, font=FONT_CODE,
                                   selectbackground=BORDER, activestyle="none", highlightthickness=0)
        self.fit_list.pack(fill=tk.X, pady=(0, PAD))
        row = tk.Frame(parent, bg=COLOR_BG)
        row.pack(fill=tk.X, pady=(0, PAD_L))
        self.repo_var = tk.StringVar()
        tk.Entry(row, textvariable=self.repo_var, bg=COLOR_DIM, fg=COLOR_TEXT, insertbackground=COLOR_TEXT,
                 font=FONT_CODE, relief=tk.FLAT).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, PAD))
        self._small_button(row, "CHECK REPO", self._check_repo).pack(side=tk.LEFT, padx=(0, PAD))
        self._small_button(row, "FIND TOP 3", self._find_models).pack(side=tk.LEFT, padx=(0, PAD))
        self.btn_download = self._small_button(row, "DOWNLOAD", self._download_model)
        self.btn_download.pack(side=tk.LEFT)
        self._fits, self._dl_cancel = [], None

    def _fit_task(self, work):
        """Run work() -> (hardware text, fits) off the Tk thread, then show the result."""
        self.lbl_fit_hw.config(text="   Checking...")
        def task():
            try:
                text, fits = work()
                self.ui_call(self._show_fits, text, fits)
            except Exception as e:  # offline, bad repo id, HF error
                self.ui_call(self._show_fits, f"   [ERROR] {e}", [])
        threading.Thread(target=task, daemon=True).start()

    def _find_models(self):
        def work():
            hw = modelfit.detect()
            return hw.summary(), [p for p in modelfit.recommend(hw, 3, resolve=True) if p.files]
        self._fit_task(work)

    def _check_repo(self):
        repo = self.repo_var.get().strip()
        def work():
            hw = modelfit.detect()
            res = modelfit.check_repo(repo, hw)
            fits = [f for f in res.candidates if f.level != modelfit.TOO_TIGHT][:8]
            note = f"{res.repo} [{res.kind}]" + ("" if fits else " - nothing in this repo fits this machine")
            return f"{hw.summary()}\n{note}", fits
        self._fit_task(work)

    def _show_fits(self, text, fits):
        self._fits = fits
        self.lbl_fit_hw.config(text=text)
        self.fit_list.delete(0, tk.END)
        for f in fits:
            self.fit_list.insert(tk.END, f"{f.name.split('/')[-1]}  ·  {f.file}  ·  {f.size_gb:.1f} GB"
                                         f"  ·  {f.level}  ·  ~{f.tps:.0f} tok/s")
        if fits:
            self.fit_list.selection_set(0)

    def _download_model(self):
        if self._dl_cancel is not None:  # second press = cancel; the .part file resumes next time
            self._dl_cancel.set()
            return
        sel = self.fit_list.curselection()
        if not sel:
            messagebox.showwarning("Get models", "Run FIND TOP 3 or CHECK REPO and pick a model first.",
                                   parent=self.root)
            return
        fit = self._fits[sel[0]]
        folder = fit.repo.split("/")[1] if fit.file.endswith(".safetensors") else ""
        self._dl_cancel = threading.Event()
        self.btn_download.config(text="CANCEL")

        def progress(done, total):
            pct = f"{done * 100 // total}%" if total else f"{done / 1024 ** 3:.2f} GB"
            self.ui_call(self._set_status, f"DOWNLOAD {fit.file}: {pct}")

        def task():
            try:
                modelfit.download_repo_files(fit.repo, fit.files, Path(MODEL_DIR) / folder, progress=progress,
                                             cancel=self._dl_cancel, total_bytes=int(fit.size_gb * 1024 ** 3))
                msg = f"MODEL | Downloaded {folder or fit.file} to models/. Pick it in the swap list."
            except modelfit.Cancelled:
                msg = "MODEL | Download cancelled; DOWNLOAD again resumes it."
            except Exception as e:
                msg = f"MODEL | Download failed: {e} (DOWNLOAD again resumes it)."
            self.ui_call(self._download_done, msg)
        threading.Thread(target=task, daemon=True).start()

    def _download_done(self, msg):
        self._dl_cancel = None
        self.btn_download.config(text="DOWNLOAD")
        self._set_status("GET MODELS: idle")
        self._populate_models()
        self.display_system_message(msg)

    def _swap_model(self):
        """Persist the pick, restart the engine on it and wait for the load (worker thread)."""
        if self._swapping:
            return
        name = self.available_models_map.get(self.model_var.get())
        if not name:
            messagebox.showwarning("Model swap", "Select a model from the list first.", parent=self.root)
            return
        if self.is_processing:
            messagebox.showinfo("Model swap", "Wait for the current reply to finish (or STOP it) first.",
                                parent=self.root)
            return
        if not messagebox.askyesno(
                "Model swap", f"Restart the engine on {name}?\n\nPeridot cannot answer until the "
                "new model has loaded, which can take a few minutes.", parent=self.root):
            return
        self._swapping = True  # handle_input queues until _swap_done
        self.btn_swap.config(state=tk.DISABLED)
        self.display_system_message(f"MODEL | Restarting the engine on {name}...")

        def task():
            try:
                status, detail = run_model_swap(
                    name, post=_engine_post, spawn=lambda: spawn_server(name), health=_health_probe,
                    sleep=time.sleep, on_status=lambda s: self.ui_call(self._set_status, s))
            except Exception as e:
                status, detail = "failed", str(e)
            tail = tail_lines(LOG_PATH / "server.log") if status == "failed" else ""
            self.ui_call(self._swap_done, name, status, detail, tail)
        threading.Thread(target=task, daemon=True).start()

    def _swap_done(self, name, status, detail, tail=""):
        self._swapping = False
        self.btn_swap.config(state=tk.NORMAL)
        if status == "ok":
            self._set_active_model(detail)
            self._set_status("FSM: ONLINE", COLOR_ACCENT)
            self.display_system_message(f"MODEL | {detail} loaded.")
        elif status == "rejected":
            self.display_system_message(f"MODEL | Swap rejected: {detail}")
        else:
            self._set_status("FSM: ENGINE OFFLINE", COLOR_ERROR)
            log = f"\nLast lines of logs/server.log:\n{tail}" if tail else ""
            self.display_system_message(f"MODEL | {name} did not load: {detail}{log}")
        self._start_next_queued()

    def _set_status(self, text, fg=AMBER):
        self.lbl_status.config(text=text, fg=fg)

    def _set_active_model(self, name):
        self.lbl_current_model.config(text=f"   {name}")

    def _refresh_active_model(self):
        """CURRENT ACTIVE MODEL from the running engine, not from config at import."""
        def task():
            h = _health_probe()
            model = h[1].get("model") if h else None
            # Engines without the /health "model" field: best guess is config's.
            self.ui_call(self._set_active_model, model or os.path.basename(str(MODEL_PATH)))
        threading.Thread(target=task, daemon=True).start()

    def _force_reclaim_vram(self):
        """Sends a signal to the engine to manually flush GC and VRAM (off the Tk thread)."""
        def task():
            try:
                resp = requests.post(f"{SERVER_URL}/vram/reclaim", headers=HEADERS, timeout=10)
                if resp.status_code == 200:
                    self.display_system_message("HARDWARE | Manual VRAM reclaim triggered successfully.")
                else:
                    self.display_system_message(f"HARDWARE | VRAM reclaim failed: {resp.text}")
            except Exception as e:
                self.display_system_message(f"HARDWARE | Could not reach neural engine: {e}")
        threading.Thread(target=task, daemon=True).start()

    # --- SHARED WIDGET BUILDERS ---
    def _input_button(self, text, command, column):
        """An input-row button: flat, 1px border (the highlight ring), hover-lit."""
        btn = tk.Button(self.in_frame, text=text, command=command, font=FONT_BUTTON,
                        padx=PAD_L, pady=PAD_S, bd=0, relief=tk.FLAT, highlightthickness=1,
                        disabledforeground=MUTED)
        btn.grid(row=2, column=column, padx=(PAD, 0), sticky="nsew")
        btn.bind("<Enter>", lambda e: self._hover_button(btn, True))
        btn.bind("<Leave>", lambda e: self._hover_button(btn, False))
        self._style_button(btn, MINT)
        return btn

    def _style_button(self, btn, fg, accent=LIME, border=BORDER, filled=False):
        """Idle: fg on SURFACE inside a border-coloured 1px ring. Hover: ring
        and text turn accent, or (filled) the button fills accent with BLACK
        text. Pressed: SURFACE_2 behind accent text; filled stays filled."""
        idle = {"fg": fg, "bg": SURFACE, "highlightbackground": border, "highlightcolor": border}
        hover = {"fg": BLACK, "bg": accent} if filled else {"fg": accent, "bg": SURFACE}
        hover.update(highlightbackground=accent, highlightcolor=accent)
        btn.config(activebackground=accent if filled else SURFACE_2,
                   activeforeground=BLACK if filled else accent)
        style = self._btn_styles.setdefault(str(btn), {"inside": False})
        style.update(idle=idle, hover=hover)
        btn.config(**(hover if style["inside"] else idle))

    def _hover_button(self, btn, inside):
        style = self._btn_styles[str(btn)]
        style["inside"] = inside
        btn.config(**(style["hover"] if inside else style["idle"]))

    def _set_send_mode(self, stop):
        """SEND (lime) while idle; STOP (red, cancels the reply) while one streams."""
        if stop:
            self.btn_send.config(text="STOP", command=self._cancel_reply, state=tk.NORMAL)
            self._style_button(self.btn_send, RED, accent=RED, border=RED, filled=True)
        else:
            self.btn_send.config(text="SEND", command=self.handle_input, state=tk.NORMAL)
            self._style_button(self.btn_send, LIME, border=LIME, filled=True)

    def _cancel_reply(self):
        if not self.is_processing:
            return
        self.btn_send.config(state=tk.DISABLED)  # one STOP per reply; _finish re-arms

        def task():
            if not core_api.post_cancel():
                self.display_system_message("STOP | The engine did not cancel the reply.")
        threading.Thread(target=task, daemon=True).start()

    def _section(self, parent, text):
        tk.Label(parent, text=text, bg=COLOR_BG, fg=MUTED, font=FONT_UI, anchor="w").pack(fill=tk.X, pady=(0, PAD))

    def _small_button(self, parent, text, command, fg=MINT):
        return tk.Button(parent, text=text, bg=COLOR_DIM, fg=fg, font=FONT_UI,
                         padx=PAD, pady=PAD_S, command=command)

    def _make_tree(self, parent, columns, height):
        """Treeview + dark scrollbar; columns = ((key, heading, width), ...)."""
        holder = tk.Frame(parent, bg=COLOR_BG)
        holder.pack(fill=tk.BOTH, expand=True, pady=(0, PAD))
        tree = ttk.Treeview(holder, columns=[c[0] for c in columns], show="headings",
                            height=height, selectmode="browse")
        for key, title, width in columns:
            tree.heading(key, text=title, anchor="w")
            tree.column(key, width=width, anchor="w", stretch=key == "description")
        scroll = ttk.Scrollbar(holder, orient=tk.VERTICAL, command=tree.yview, style="Vertical.TScrollbar")
        tree.config(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        return tree

    # --- SETTINGS: ALLOWLIST / WEB / INVOCATION ---
    def _build_settings_extras(self, parent):
        entry_kw = dict(bg=SURFACE, fg=MINT, font=FONT_CODE, insertbackground=LIME, relief=tk.FLAT,
                        highlightthickness=1, highlightcolor=LIME, highlightbackground=BORDER)

        self._section(parent, ">> ALLOWLISTED FOLDERS (SOVEREIGN INVOCATION):")
        self.folder_list = tk.Listbox(
            parent, height=5, bg=SURFACE, fg=MINT, font=FONT_CODE, bd=0, relief=tk.FLAT,
            highlightthickness=1, highlightcolor=BORDER, highlightbackground=BORDER,
            selectbackground=SURFACE_2, selectforeground=LIME, activestyle="none")
        self.folder_list.pack(fill=tk.X, pady=(0, PAD))
        row = tk.Frame(parent, bg=COLOR_BG)
        row.pack(fill=tk.X, pady=(0, PAD_L))
        for text, cmd in (("ADD", self._add_folder), ("REMOVE", self._remove_folder),
                          ("TOGGLE WRITE", self._toggle_folder_write)):
            self._small_button(row, text, cmd).pack(side=tk.LEFT, padx=(0, PAD))
        tk.Frame(parent, bg=BORDER, height=1).pack(fill=tk.X, pady=(0, PAD_L))

        self._section(parent, ">> WEB SEARCH (BETA):")
        tk.Label(parent, text="SearXNG URL (optional; blank = DuckDuckGo)", bg=COLOR_BG, fg=MINT,
                 font=FONT_UI, anchor="w").pack(fill=tk.X)
        row = tk.Frame(parent, bg=COLOR_BG)
        row.pack(fill=tk.X, pady=PAD_S)
        self.searxng_var = tk.StringVar()
        self.searxng_entry = tk.Entry(row, textvariable=self.searxng_var, selectbackground=GRAPE,
                                      selectforeground=MINT, **entry_kw)
        self.searxng_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=PAD_S)
        self._small_button(row, "SAVE", self._save_searxng).pack(side=tk.LEFT, padx=(PAD, 0))
        tk.Label(parent, text="Privacy: while web search is on, the model's search queries go to "
                              "DuckDuckGo or your SearXNG server. Off by default.",
                 bg=COLOR_BG, fg=MUTED, font=FONT_SMALL, anchor="w", justify=tk.LEFT,
                 wraplength=440).pack(fill=tk.X, pady=(0, PAD_L))
        tk.Frame(parent, bg=BORDER, height=1).pack(fill=tk.X, pady=(0, PAD_L))

        self._section(parent, ">> SOVEREIGN INVOCATION:")
        grid = tk.Frame(parent, bg=COLOR_BG)
        grid.pack(fill=tk.X, pady=(0, PAD))
        self.idle_min_var = tk.StringVar(value="5")
        self.review_s_var = tk.StringVar(value="120")
        for r, (label, var, lo, hi) in enumerate((
                ("Unload model after idle (minutes)", self.idle_min_var, 1, 1440),
                ("Review dialog timeout (seconds)", self.review_s_var, 10, 3600))):
            tk.Label(grid, text=label, bg=COLOR_BG, fg=MINT, font=FONT_UI, anchor="w").grid(
                row=r, column=0, sticky="w", pady=2)
            tk.Spinbox(grid, from_=lo, to=hi, textvariable=var, width=6, buttonbackground=SURFACE_2,
                       **entry_kw).grid(row=r, column=1, sticky="w", padx=(PAD, 0), pady=2)
        row = tk.Frame(parent, bg=COLOR_BG)
        row.pack(fill=tk.X, pady=(0, PAD))
        self._small_button(row, "SAVE", self._save_invocation).pack(side=tk.LEFT, padx=(0, PAD))
        self._small_button(row, "COPY MCP SETUP", self._copy_mcp_setup, fg=LIME).pack(side=tk.LEFT)

    def _load_settings(self):
        def task():
            self.ui_call(self._apply_settings, core_api.get_settings(), None)
        threading.Thread(target=task, daemon=True).start()

    def _post_settings(self, changes, label):
        """POST off the Tk thread; widgets then follow the server's reply."""
        def task():
            self.ui_call(self._apply_settings, core_api.post_settings(changes), label)
        threading.Thread(target=task, daemon=True).start()

    def _apply_settings(self, s, label=None):
        """Tk thread: mirror a GET/POST /settings reply into every widget."""
        if "error" in s:
            if label:
                self.display_system_message(f"SETTINGS | {label} not saved: {s['error']}")
                self._load_settings()  # put the widgets back to what the server has
            return
        self.web_enabled = bool(s.get("web.enabled"))
        self.btn_web.config(text=f"WEB: {'ON' if self.web_enabled else 'OFF'}",
                            fg=LIME if self.web_enabled else MUTED)
        self._set_web_armed(self.web_armed and self.web_enabled)

        self._allow_folders = [f for f in s.get("allow.folders", [])
                               if isinstance(f, dict) and isinstance(f.get("path"), str)]
        self.folder_list.delete(0, tk.END)
        for f in self._allow_folders:
            self.folder_list.insert(tk.END, f" [{'RW' if f.get('write') else 'R '}] {f['path']}")
        if not self._allow_folders:
            self.folder_list.insert(tk.END, " [EMPTY] Peridot can read no folders yet.")

        self.searxng_var.set(s.get("web.searxng_url", ""))
        self.idle_min_var.set(str(max(1, int(s.get("invocation.idle_unload_s", 300)) // 60)))
        self.review_s_var.set(str(int(s.get("invocation.review_timeout_s", 120))))
        self.model_invoke_var.set(bool(s.get("extensions.model_invoke", True)))
        if label:
            self.display_system_message(f"SETTINGS | {label} saved.")

    def _selected_folder(self):
        sel = self.folder_list.curselection()
        return sel[0] if sel and sel[0] < len(self._allow_folders) else None

    def _add_folder(self):
        path = filedialog.askdirectory(parent=self.root, title="Allowlist a folder for Sovereign Invocation")
        if not path:
            return
        path = os.path.normpath(path)
        ok, why = is_file_safe(path)
        if not ok:
            self.display_system_message(f"ALLOWLIST | {why}")
            return
        if any(os.path.normcase(f["path"]) == os.path.normcase(path) for f in self._allow_folders):
            self.display_system_message(f"ALLOWLIST | {path} is already allowlisted.")
            return
        self._post_settings({"allow.folders": self._allow_folders + [{"path": path, "write": False}]},
                            "Allowlist")

    def _remove_folder(self):
        i = self._selected_folder()
        if i is not None:
            self._post_settings({"allow.folders": [f for j, f in enumerate(self._allow_folders) if j != i]},
                                "Allowlist")

    def _toggle_folder_write(self):
        i = self._selected_folder()
        if i is None:
            return
        folders = [dict(f) for f in self._allow_folders]
        want = not folders[i].get("write")
        if want and not messagebox.askyesno(
                "Allow writes",
                f"Let Peridot create and overwrite files in:\n\n{folders[i]['path']}\n\n"
                "Only enable this for folders you are happy for the model to change.",
                icon="warning", parent=self.root):
            return
        folders[i]["write"] = want
        self._post_settings({"allow.folders": folders}, "Allowlist")

    def _save_searxng(self):
        url = self.searxng_var.get().strip()
        if url and not re.match(r"https?://\S+$", url):
            self.display_system_message("WEB | SearXNG URL must start with http:// or https:// (or be blank).")
            return
        self._post_settings({"web.searxng_url": url}, "SearXNG URL")

    def _save_invocation(self):
        try:
            minutes, review = int(self.idle_min_var.get()), int(self.review_s_var.get())
        except ValueError:
            self.display_system_message("INVOCATION | Idle minutes and review seconds must be whole numbers.")
            return
        self._post_settings({"invocation.idle_unload_s": max(1, minutes) * 60,
                             "invocation.review_timeout_s": max(10, review)}, "Sovereign Invocation")

    def _copy_mcp_setup(self):
        cmd = mcp_setup_command(BASE_DIR, venv_python(BASE_DIR))
        self.root.clipboard_clear()
        self.root.clipboard_append(cmd)
        self.display_system_message(f"MCP | Copied the Claude Code setup command:\n{cmd}\n"
                                    "For Codex CLI and Gemini CLI see mcp/README.md.")

    # --- WEB SEARCH TOGGLES ---
    def _toggle_web(self):
        """Status-bar WEB: enabling needs an installed, approved web_search plugin."""
        want = not self.web_enabled

        def task():
            if want:
                try:
                    status = self._extensions_snapshot()["plugins"].get("web_search", {}).get("status")
                except Exception as e:
                    status = f"scan failed: {e}"
                if status != "Approved":
                    self.display_system_message(
                        "WEB | Web search needs the web_search plugin installed and approved "
                        f"(currently: {status or 'not installed'}). Open the EXTENSIONS tab, "
                        "click INSTALL BUNDLED WEB SEARCH if shown, then select it and APPROVE.")
                    self.ui_call(self.notebook.select, self.tab_extensions)
                    return
            self.ui_call(self._apply_settings, core_api.post_settings({"web.enabled": want}), "Web search")
        threading.Thread(target=task, daemon=True).start()

    def _toggle_web_armed(self):
        if not self.web_enabled:
            self.display_system_message("WEB | Web search is off. Turn on WEB in the status bar first.")
            return
        self._set_web_armed(not self.web_armed)

    def _set_web_armed(self, armed):
        self.web_armed = armed
        self.btn_search.config(text="[x] SEARCH" if armed else "[ ] SEARCH")
        self._style_button(self.btn_search, LIME if armed else (MINT if self.web_enabled else MUTED),
                           border=LIME if armed else BORDER)

    # --- ATTACHMENTS ---
    def _attach_files(self):
        paths = filedialog.askopenfilenames(parent=self.root, title="Attach files")
        if not paths:
            return
        budget = INPUT_MAX_CHARS - len(self.entry.get("1.0", "end-1c"))

        def task():
            room, pdfs = budget, []
            for path in paths:
                name = os.path.basename(path)
                ok, why = is_file_safe(path)
                if not ok:
                    self.display_system_message(f"ATTACH | {name} refused: {why}")
                    continue
                try:
                    kind, value = read_attachment(path)
                except OSError as e:
                    self.display_system_message(f"ATTACH | Could not read {name}: {e}")
                    continue
                if kind == "pdf":
                    pdfs.append(path)
                elif kind == "text":
                    limit = min(ATTACH_MAX_CHARS, room - 120 - len(name))  # header/fence/note
                    if limit < 200:
                        self.display_system_message(
                            f"ATTACH | {name} skipped: the message is at the "
                            f"{INPUT_MAX_CHARS:,}-character limit.")
                        continue
                    block = format_attachment(name, value, limit)
                    room -= len(block) + 1
                    self.ui_call(self._insert_attachment, block)
                else:
                    self.display_system_message(f"ATTACH | {value}")
            if pdfs:
                self._ingest_pdfs(pdfs)
        threading.Thread(target=task, daemon=True).start()

    def _insert_attachment(self, block):
        if self.entry.get("1.0", "end-1c").strip():
            block = "\n" + block
        self.entry.insert(tk.END, block)
        self._adjust_input_height()

    def _ingest_pdfs(self, paths):
        """Worker thread: copy PDFs into input/ and have the server ingest them. No Tk."""
        copied = []
        for path in paths:
            name = os.path.basename(path)
            dst = Path(INPUT_PATH) / name
            try:
                if Path(path).resolve() != dst.resolve():
                    shutil.copy2(path, dst)
                copied.append(name)
            except OSError as e:
                self.display_system_message(f"ATTACH | Could not copy {name} into the Vault inbox: {e}")
        if not copied:
            return
        self.display_system_message(f"ATTACH | Ingesting {', '.join(copied)}...")
        try:
            self.core.ingest_via_server()
        except Exception as e:
            self.display_system_message(f"ATTACH | Ingestion failed: {e}")
            return
        for name in copied:
            self.display_system_message(f"Ingested into Vault: {name}")

    # --- EXTENSIONS TAB ---
    def _build_extensions_tab(self):
        frame = tk.Frame(self.tab_extensions, bg=COLOR_BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=PAD_L * 2, pady=PAD_L)

        self.model_invoke_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            frame, text="Let the model use skills and plugins automatically",
            variable=self.model_invoke_var, command=self._toggle_model_invoke,
            bg=COLOR_BG, fg=MINT, selectcolor=SURFACE, activebackground=COLOR_BG,
            activeforeground=LIME, font=FONT_UI, anchor="w", highlightthickness=0, bd=0,
        ).pack(fill=tk.X, pady=(0, PAD_L))

        self._section(frame, ">> SKILLS  (double-click or USE to start a message with /name)")
        self.skills_tree = self._make_tree(
            frame, (("name", "NAME", 180), ("description", "DESCRIPTION", 600)), height=4)
        self.skills_tree.bind("<Double-1>", self._use_skill)
        row = tk.Frame(frame, bg=COLOR_BG)
        row.pack(fill=tk.X, pady=(0, PAD_L))
        self._small_button(row, "USE", self._use_skill, fg=LIME).pack(side=tk.LEFT)

        self._section(frame, ">> PLUGINS")
        self.plugins_tree = self._make_tree(
            frame, (("name", "NAME", 140), ("version", "VERSION", 70), ("status", "STATUS", 180),
                    ("perms", "PERMISSIONS", 230), ("description", "DESCRIPTION", 400)), height=4)
        self.plugins_tree.tag_configure("ok", foreground=LIME)
        self.plugins_tree.tag_configure("changed", foreground=AMBER)
        self.plugins_tree.tag_configure("pending", foreground=MINT)
        row = tk.Frame(frame, bg=COLOR_BG)
        row.pack(fill=tk.X, pady=(0, PAD_L))
        for text, cmd, fg in (("APPROVE", self._approve_plugin, LIME), ("REVOKE", self._revoke_plugin, RED),
                              ("RELOAD", lambda: self._refresh_extensions(force=True), MINT),
                              ("OPEN FOLDER", self._open_extensions_folder, MINT)):
            self._small_button(row, text, cmd, fg=fg).pack(side=tk.LEFT, padx=(0, PAD))
        # Packed only while extensions/plugins/web_search is absent.
        self.btn_install_web = self._small_button(row, "INSTALL BUNDLED WEB SEARCH", self._install_web_search)

        self._section(frame, ">> LOAD ERRORS")
        self.ext_errors = tk.Listbox(
            frame, height=3, bg=COLOR_BG, fg=MUTED, font=FONT_SYSTEM, bd=0, relief=tk.FLAT,
            highlightthickness=0, selectbackground=SURFACE_2, selectforeground=MINT, activestyle="none")
        self.ext_errors.pack(fill=tk.X)

    def _extensions_snapshot(self, force=False):
        """Worker thread: registry + approval state as plain data. No Tk."""
        reg = registry.rescan() if force else registry.scan()
        s = core_api.get_settings()
        approved = (local_settings.get("plugins.approved") if "error" in s
                    else s.get("plugins.approved") or {})
        plugins = {}
        for p in reg.plugins.values():
            plugins[p.name] = {
                "name": p.name, "version": p.version, "description": p.description,
                "permissions": dict(p.permissions), "tools": [t["name"] for t in p.tools],
                "hash": p.hash, "status": plugin_status(p.name, p.hash, approved),
            }
        return {
            "skills": [(sk.name, sk.description) for sk in reg.skills.values()],
            "plugins": plugins,
            "errors": list(reg.errors),
            "settings": s,
            "web_installed": (registry.EXTENSIONS_DIR / "plugins" / "web_search").exists(),
        }

    def _refresh_extensions(self, force=False):
        def task():
            try:
                snap = self._extensions_snapshot(force)
            except Exception as e:
                self.display_system_message(f"EXTENSIONS | Scan failed: {e}")
                return
            self.ui_call(self._apply_extensions, snap)
        threading.Thread(target=task, daemon=True).start()

    def _apply_extensions(self, snap):
        """Tk thread: render an _extensions_snapshot()."""
        self._ext_snapshot = snap
        self.skills_tree.delete(*self.skills_tree.get_children())
        for name, desc in snap["skills"]:
            self.skills_tree.insert("", tk.END, iid=name, values=(name, desc))

        tags = {"Approved": "ok", "Changed since approval": "changed", "Needs approval": "pending"}
        self.plugins_tree.delete(*self.plugins_tree.get_children())
        for p in snap["plugins"].values():
            self.plugins_tree.insert("", tk.END, iid=p["name"], tags=(tags[p["status"]],), values=(
                p["name"], p["version"], p["status"], perm_summary(p["permissions"]), p["description"]))

        self.ext_errors.delete(0, tk.END)
        for err in snap["errors"] or ["None."]:
            self.ext_errors.insert(tk.END, f" {err}")

        if snap["web_installed"]:
            self.btn_install_web.pack_forget()
        else:
            self.btn_install_web.pack(side=tk.LEFT, padx=(0, PAD))
        self._apply_settings(snap["settings"])

    def _use_skill(self, event=None):
        sel = self.skills_tree.selection()
        if not sel:
            return
        prefix = f"/{sel[0]} "
        self.entry.insert("1.0", prefix)
        self.entry.mark_set(tk.INSERT, f"1.0 + {len(prefix)} chars")
        self.notebook.select(self.tab_chat)
        self.entry.focus_set()
        self._adjust_input_height()

    def _selected_plugin(self):
        sel = self.plugins_tree.selection()
        if not sel or not self._ext_snapshot:
            self.display_system_message("EXTENSIONS | Select a plugin first.")
            return None
        return self._ext_snapshot["plugins"].get(sel[0])

    def _approve_plugin(self):
        p = self._selected_plugin()
        if p is None:
            return
        if p["status"] == "Approved":
            self.display_system_message(f"EXTENSIONS | {p['name']} is already approved.")
            return
        perms = p["permissions"]
        files = "your allowlisted folders" if perms.get("files") == "allowlist" else "none"
        msg = (f"Approve {p['name']} v{p['version']}?\n\n{p['description']}\n\n"
               f"Permissions:\n  Network access: {'YES' if perms.get('network') else 'no'}\n"
               f"  Files: {files}\n\nTools:\n  " + "\n  ".join(p["tools"]) +
               "\n\nIt runs in Peridot's plugin sandbox. Any change to its files "
               "drops it back to unapproved.")
        if messagebox.askyesno("Approve plugin", msg, icon="warning", parent=self.root):
            self._set_plugin_approval(p["name"], p["hash"])

    def _revoke_plugin(self):
        p = self._selected_plugin()
        if p is None:
            return
        if p["status"] == "Needs approval":
            self.display_system_message(f"EXTENSIONS | {p['name']} is not approved.")
            return
        self._set_plugin_approval(p["name"], None)

    def _set_plugin_approval(self, name, digest):
        """digest=None revokes. Pins the hash the user reviewed, not a fresh one,
        so files changed after the dialog opened stay unapproved."""
        def task():
            current = core_api.get_settings()
            if "error" in current:
                self.display_system_message(f"EXTENSIONS | Not saved: {current['error']}")
                return
            approved = {k: v for k, v in (current.get("plugins.approved") or {}).items() if k != name}
            if digest:
                approved[name] = digest
            result = core_api.post_settings({"plugins.approved": approved})
            if "error" in result:
                self.display_system_message(f"EXTENSIONS | Not saved: {result['error']}")
                return
            self.display_system_message(f"EXTENSIONS | {name} {'approved' if digest else 'revoked'}.")
            self.ui_call(self._apply_extensions, self._extensions_snapshot())
        threading.Thread(target=task, daemon=True).start()

    def _toggle_model_invoke(self):
        self._post_settings({"extensions.model_invoke": bool(self.model_invoke_var.get())},
                            "Automatic skill/plugin use")

    def _open_extensions_folder(self):
        def task():
            root = registry.EXTENSIONS_DIR
            try:
                for sub in ("skills", "plugins"):
                    (root / sub).mkdir(parents=True, exist_ok=True)
                if sys.platform == "win32":
                    os.startfile(root)
                else:
                    subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(root)])
            except Exception as e:
                self.display_system_message(f"EXTENSIONS | Could not open {root}: {e}")
        threading.Thread(target=task, daemon=True).start()

    def _install_web_search(self):
        def task():
            src = Path(registry.__file__).parent / "bundled" / "web_search"
            dst = registry.EXTENSIONS_DIR / "plugins" / "web_search"
            try:
                if not dst.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
                snap = self._extensions_snapshot(force=True)
            except Exception as e:
                self.display_system_message(f"EXTENSIONS | Install failed: {e}")
                return
            self.display_system_message(
                "EXTENSIONS | web_search installed (not yet approved). Select it and click APPROVE.")
            self.ui_call(self._apply_extensions, snap)
        threading.Thread(target=task, daemon=True).start()

    def _bind_shortcuts(self):
        """Global key bindings for UX navigation."""
        self.root.bind("<Control-Key-1>", lambda e: self.notebook.select(0))
        self.root.bind("<Control-Key-2>", lambda e: self.notebook.select(1))
        self.root.bind("<Control-Key-3>", lambda e: self.notebook.select(2))
        self.root.bind("<Control-Key-4>", lambda e: self.notebook.select(3))
        self.root.bind("<Control-f>", self._toggle_search)
        self.root.bind("<Control-F>", self._toggle_search)
        self.root.bind("<Control-R>", lambda e: self._toggle_research())
        self.root.bind("<Control-r>", lambda e: self._toggle_research())

    def _toggle_search(self, event=None):
        if self.search_frame.winfo_ismapped():
            self._close_search()
        else:
            self.search_frame.pack(fill=tk.X, before=self.notebook)
            self.search_entry.focus_set()

    def _close_search(self, event=None):
        self.search_frame.pack_forget()
        self.chat.tag_remove("search", "1.0", tk.END)
        self.entry.focus_set()

    def _execute_search(self, event=None):
        """Real-time indexing over active text buffer."""
        self.chat.tag_remove("search", "1.0", tk.END)
        query = self.search_entry.get()
        if not query: return
        
        start_idx = "1.0"
        while True:
            pos = self.chat.search(query, start_idx, stopindex=tk.END, nocase=True)
            if not pos:
                break
            end_idx = f"{pos}+{len(query)}c"
            self.chat.tag_add("search", pos, end_idx)
            start_idx = end_idx

    def _add_monitor(self, lbl, var):
        f = tk.Frame(self.stat_bar, bg=SURFACE)
        f.pack(side=tk.RIGHT, padx=(0, PAD_L), pady=PAD)
        tk.Label(f, text=lbl, bg=SURFACE, fg=MUTED, font=FONT_UI).pack(side=tk.LEFT, padx=(0, PAD_S))
        b = TechProgressBar(f, width=90, height=16, bg=BORDER)
        b.pack(side=tk.LEFT)
        setattr(self, var, b)

    def _configure_styles(self):
        # Messages read as blocks: space above each turn, a little leading
        # inside wrapped lines, AI text indented under the user's prompt.
        self.chat.tag_config("user", foreground=COLOR_USER, font=FONT_BOLD,
                             spacing1=PAD, spacing2=2, spacing3=PAD_S, lmargin1=0, lmargin2=PAD_L)
        self.chat.tag_config("ai", foreground=COLOR_AI, font=FONT_MAIN,
                             spacing1=2, spacing2=3, spacing3=2, lmargin1=PAD, lmargin2=PAD, rmargin=PAD)
        self.chat.tag_config("system", foreground=COLOR_SYSTEM, font=FONT_SYSTEM,
                             spacing1=2, spacing3=2)
        self.chat.tag_config("logo", foreground=COLOR_ACCENT, font=FONT_LOGO, justify="center")
        self.chat.tag_config("code_block", font=FONT_CODE, foreground=MINT, background=COLOR_CODE_BG,
                             lmargin1=PAD_L, lmargin2=PAD_L, rmargin=PAD, spacing1=1, spacing3=1)
        self.chat.tag_config("search", background=AMBER, foreground=BLACK)
        self.chat.tag_config("tool", foreground=MUTED, font=FONT_SYSTEM, lmargin1=PAD, lmargin2=PAD)
        self.chat.tag_config("stopped", foreground=MUTED, font=FONT_SMALL)

        self.entry.tag_config("misspelled", underline=True, underlinefg=COLOR_ERROR)

    # --- KINETIC SMOOTH SCROLLING PIPELINE ---
    def _on_kinetic_scroll(self, event):
        """Intercepts raw OS wheel events to populate the kinetic velocity vector."""
        delta = event.delta / 120.0
        self.chat_scroll_velocity -= delta * 50.0 
        
        if not self.chat_scroll_animating:
            self._animate_smooth_scroll()
            
        return "break"

    def _animate_smooth_scroll(self):
        """~60fps animation loop; stops itself once the velocity has decayed."""
        if abs(self.chat_scroll_velocity) < 1.0:
            self.chat_scroll_velocity = 0.0
            self.chat_scroll_animating = False
            return

        self.chat_scroll_animating = True

        # 0.4 per 16ms frame ~= the old 0.15 per 5ms frame (0.85^3.2 ~= 0.6),
        # so the glide distance and feel are unchanged at a third of the wakeups.
        step = self.chat_scroll_velocity * 0.4
        pixel_step = int(step)
        if pixel_step == 0:
            pixel_step = 1 if step > 0 else -1
            
        try:
            self.chat.yview_scroll(pixel_step, "pixels")
        except Exception:
            self.chat.yview_scroll(1 if pixel_step > 0 else -1, "units")
            self.chat_scroll_velocity = 0
            self.chat_scroll_animating = False
            return
            
        self.chat_scroll_velocity -= step
        self.root.after(16, self._animate_smooth_scroll)

    def _on_tab_changed(self, event):
        tab = self.notebook.nametowidget(self.notebook.select())
        if tab is self.tab_vault:
            self._update_vault_directory()
        elif tab is self.tab_extensions:
            self._refresh_extensions()
        elif tab is self.tab_settings:
            self._load_settings()

    def _update_vault_directory(self):
        self.vault_list.delete(0, tk.END)
        
        vault_dir = Path("input") / "processed"
        fallback_dir = Path("input")

        if vault_dir.exists():
            files = sorted(f.name for f in vault_dir.iterdir() if f.is_file())
            if not files:
                self.vault_list.insert(tk.END, " [EMPTY] No text corpora or source files detected inside archived sectors.")
            for file in files:
                self.vault_list.insert(tk.END, f" └── [SECURED-VAULT-NODE] : {file}")
        elif fallback_dir.exists():
            files = sorted(f.name for f in fallback_dir.iterdir() if f.is_file())
            if files:
                for file in files:
                    self.vault_list.insert(tk.END, f" └── [STAGED-NODE] : {file}")
                return
            self.vault_list.insert(tk.END, " [EMPTY] Vector directories are completely unmapped.")
        else:
            self.vault_list.insert(tk.END, " [ERROR] Physical storage path roots are missing.")

    # --- SESSION SIDEBAR HANDLERS ---
    def _toggle_session_drawer(self):
        """Toggle the collapsible session sidebar drawer."""
        if self.session_drawer_open:
            # Hide the sidebar and reset the window layout
            self.chat_pane.forget(self.session_frame)
            self.btn_toggle_sessions.config(text="[>] SESSIONS")
            self.session_drawer_open = False
        else:
            self._refresh_session_list()
            # The critical fix: We must add the frame *before* the chat matrix frame
            self.chat_pane.add(self.session_frame, before=self.chat_frame, minsize=200, width=250)
            self.btn_toggle_sessions.config(text="[<] CLOSE SESSIONS")
            self.session_drawer_open = True

    def _new_session(self):
        """Create a new chat session and refresh the sidebar."""
        try:
            self.core.create_new_session()
            self._refresh_session_list()
            self.clear_chat()
            self.display_system_message("New session created.")
        except Exception as e:
            self.display_system_message(f"Session creation failed: {e}")

    def _delete_session(self):
        """Delete the right-clicked session."""
        if self._current_session_menu_index is None:
            return
        try:
            session = self.display_mapping[self._current_session_menu_index]
            if not session: return
            sid = session["session_id"]
            if self.core.current_session_id == sid:
                self.clear_chat()
            self.core.delete_session(sid)
            self._refresh_session_list()
        except Exception as e:
            self.display_system_message(f"Session deletion failed: {e}")
        finally:
            self._current_session_menu_index = None

    def _rename_session(self):
        if self._current_session_menu_index is None: return
        try:
            session = self.display_mapping[self._current_session_menu_index]
            if not session: return
            sid = session["session_id"]
            current_title = session.get("title", "Untitled")
            
            # Custom stylized modal dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("RENAME SESSION")
            dialog.configure(bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
            dialog.geometry("350x120")
            dialog.resizable(False, False)
            dialog.transient(self.root)
            dialog.grab_set()

            # Center relative to root window
            x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 175
            y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 60
            dialog.geometry(f"+{x}+{y}")

            lbl = tk.Label(dialog, text="[ ENTER NEW SESSION TITLE ]", font=FONT_UI, fg=MUTED, bg=SURFACE)
            lbl.pack(pady=(PAD_L, PAD))

            entry = tk.Entry(dialog, font=FONT_MAIN, bg=SURFACE_2, fg=MINT, insertbackground=LIME, relief=tk.FLAT,
                             highlightthickness=1, highlightcolor=LIME, highlightbackground=BORDER,
                             selectbackground=GRAPE, selectforeground=MINT)
            entry.insert(0, current_title)
            entry.pack(fill=tk.X, padx=PAD_L, pady=PAD_S, ipady=PAD_S)
            entry.focus_set()
            entry.select_range(0, tk.END)

            new_title = [None]
            
            def on_submit(event=None):
                new_title[0] = entry.get()
                dialog.destroy()

            def on_cancel(event=None):
                dialog.destroy()

            entry.bind("<Return>", on_submit)
            dialog.bind("<Escape>", on_cancel)

            self.root.wait_window(dialog)

            if new_title[0] and new_title[0].strip() and new_title[0].strip() != current_title:
                self.core.chat_ledger.update_session_title(sid, new_title[0].strip())
                self._refresh_session_list()
        except Exception as e:
            self.display_system_message(f"Session rename failed: {e}")
        finally:
            self._current_session_menu_index = None

    def _show_session_menu(self, event):
        """Show right-click context menu on session list."""
        try:
            index = self.session_listbox.nearest(event.y)
            if index >= 0 and hasattr(self, 'display_mapping') and index < len(self.display_mapping):
                if self.display_mapping[index] is None:
                    return
                self._current_session_menu_index = index
                self.session_listbox.selection_clear(0, tk.END)
                self.session_listbox.selection_set(index)
                self.session_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.session_menu.grab_release()

    def _on_session_select(self, event):
        """Handle session selection from sidebar Listbox."""
        try:
            index = self.session_listbox.curselection()
            if not index:
                return
            idx = index[0]
            if not hasattr(self, 'display_mapping') or idx < 0 or idx >= len(self.display_mapping):
                return
            session = self.display_mapping[idx]
            if not session:
                self.session_listbox.selection_clear(idx)
                return
            session_id = session["session_id"]
            if session_id == self.core.current_session_id:
                return
            self.core.switch_session(session_id)
            full_history = self.core.get_session_history(session_id, full=True)
            self._replay_history(full_history)
            self._refresh_session_list()
            self.display_system_message(f"Switched to session: {session.get('title', 'Untitled')[:40]}")
        except Exception as e:
            self.display_system_message(f"Session switch failed: {e}")

    def _replay_history(self, history):
        """Clear chat widget and replay full session history."""
        self.clear_chat()
        if not history:
            return
        for msg in history:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                self.write(f"\n> {content}\n", "user")
            elif role == "assistant":
                self._parse_and_write_ai(content, reasoning=msg.get("reasoning") or "")
        self.chat.see(tk.END)

    def _refresh_session_list(self):
        """Refresh the session Listbox from core."""
        try:
            self.sessions = self.core.list_sessions(100)
            self.session_listbox.delete(0, tk.END)
            self.display_mapping = []
            
            from datetime import datetime, timedelta
            now = datetime.now()
            today = now.date()
            yesterday = today - timedelta(days=1)
            last_week = today - timedelta(days=7)
            
            categories = {"TODAY": [], "YESTERDAY": [], "LAST WEEK": [], "OLDER": []}
            
            for s in self.sessions:
                try:
                    ts = s.get("updated_at", 0)
                    dt = datetime.fromtimestamp(ts).date()
                    if dt == today:
                        categories["TODAY"].append(s)
                    elif dt == yesterday:
                        categories["YESTERDAY"].append(s)
                    elif dt > last_week:
                        categories["LAST WEEK"].append(s)
                    else:
                        categories["OLDER"].append(s)
                except Exception:
                    categories["OLDER"].append(s)
                    
            for cat, items in categories.items():
                if not items: continue
                self.session_listbox.insert(tk.END, f" --- {cat} --- ")
                self.display_mapping.append(None)
                
                for s in items:
                    title = s.get("title", "Untitled")[:40]
                    display = f"{'[*]' if s['session_id'] == self.core.current_session_id else '[ ]'} {title}"
                    self.session_listbox.insert(tk.END, display)
                    self.display_mapping.append(s)
        except Exception as e:
            print(f"[UI] Session list refresh failed: {e}")

    # --- SPELLCHECK ARBITRATION ---
    def _load_spellchecker(self):
        """Build the UK dictionary on a worker thread; hand it over via ui_call."""
        def task():
            try:
                spell = SpellChecker(language='en')
                system_words = ["python", "fastapi", "sqlalchemy", "pydantic", "sqlite", "vram", "peridot"]
                us_variants = [
                    "color", "flavor", "behavior", "harbor", "honor", "humor", "labor", "neighbor",
                    "rumor", "splendor", "analyze", "apologize", "organize", "recognize", "realize",
                    "center", "meter", "theater", "defense", "offense", "traveler", "dialog"
                ]
                uk_variants = [
                    "colour", "flavour", "behaviour", "harbour", "honour", "humour", "labour", "neighbour",
                    "rumour", "splendour", "analyse", "apologise", "organise", "recognise", "realise",
                    "centre", "metre", "theatre", "defence", "offence", "traveller", "dialogue"
                ]
                spell.word_frequency.remove_words(us_variants)
                spell.word_frequency.load_words(uk_variants + system_words)
            except Exception as e:
                print(f"[UI] Spellcheck dictionary failed to load: {e}")
                return
            self.ui_call(setattr, self, "spell", spell)
        threading.Thread(target=task, daemon=True).start()

    def _run_spellcheck(self):
        if self.spell is None:
            return

        self.entry.tag_remove("misspelled", "1.0", tk.END)
        content = self.entry.get("1.0", "end-1c")
        # Only the tail: a pasted wall of text should not be rescanned on every
        # pause. Start on a word boundary so the first word is not cut in half.
        offset = 0
        if len(content) > 2000:
            offset = content.rfind(" ", 0, len(content) - 2000) + 1

        for match in re.finditer(r'\b[a-zA-Z]+\b', content[offset:]):
            word = match.group()
            if len(word) > 2 and word.lower() not in self.spell:
                self.entry.tag_add("misspelled", f"1.0 + {offset + match.start()} chars",
                                   f"1.0 + {offset + match.end()} chars")

    def _apply_correction(self, start, end, correct_word):
        self.entry.delete(start, end)
        self.entry.insert(start, correct_word)
        self._run_spellcheck()

    def _show_spellcheck_menu(self, event):
        if self.spell is None:
            return

        try:
            index = self.entry.index(f"@{event.x},{event.y}")
            tags = self.entry.tag_names(index)

            if "misspelled" in tags:
                menu = tk.Menu(self.root, tearoff=0)  # colours: *Menu option defaults
                
                start = self.entry.index(f"{index} wordstart")
                end = self.entry.index(f"{index} wordend")
                target_word = self.entry.get(start, end)

                candidates = self.spell.candidates(target_word.lower())
                
                if candidates:
                    for idx, candidate in enumerate(candidates):
                        if idx > 4: break
                        menu.add_command(
                            label=candidate, 
                            command=lambda c=candidate, s=start, e=end: self._apply_correction(s, e, c)
                        )
                else:
                    menu.add_command(label="No UK suggestions", state=tk.DISABLED)
                    
                menu.add_separator()
                menu.add_command(
                    label="Add to System Dictionary", 
                    command=lambda w=target_word: self.spell.word_frequency.load_words([w.lower()]) or self._run_spellcheck()
                )
                
                menu.tk_popup(event.x_root, event.y_root)
        except Exception:
            pass

    # --- INPUT HANDLERS ---
    def _on_enter(self, event):
        self.handle_input()
        return "break"

    def _on_shift_enter(self, event):
        return

    def _on_key_release(self, event):
        self._adjust_input_height()
        if not self.is_processing:
            if hasattr(self, '_spellcheck_timer'):
                self.root.after_cancel(self._spellcheck_timer)
            self._spellcheck_timer = self.root.after(500, self._run_spellcheck)

    def _adjust_input_height(self, event=None):
        # `count -displaylines` lays out the lines it measures itself, so no
        # update_idletasks (a full geometry pass) per keystroke.
        dl = self.entry.count("1.0", "end-1c", "displaylines")
        if isinstance(dl, tuple):
            dl = dl[0]
        new_height = min(max(1, (dl or 0) + 1), 8)
        if new_height != self._entry_height:
            self._entry_height = new_height
            self.entry.config(height=new_height)
        self.entry.see(tk.INSERT)

    def handle_input(self):
        t = self.entry.get("1.0", tk.END).strip()
        if not t: return
        if len(t) > INPUT_MAX_CHARS:
            # sanitize_input would refuse it with a misleading security block.
            self.display_system_message(
                f"Message is {len(t):,} characters; the limit is {INPUT_MAX_CHARS:,}. Shorten it and send again.")
            return
        web = self.web_armed  # one message only
        self._set_web_armed(False)

        self.entry.delete("1.0", tk.END)
        self._adjust_input_height()
        self.entry.tag_remove("misspelled", "1.0", tk.END)

        if self.is_processing or self._swapping:
            # Busy: hold it (with its own web flag) until the reply ends.
            self._queue.enqueue(t, web)
            self._render_queue()
            return
        self.write(f"\n> {t}\n", "user")
        self._process_async(t, web=web)

    def _start_next_queued(self):
        """Send the oldest queued prompt, if idle. Tk thread."""
        if self.is_processing or self._swapping:
            return
        item = self._queue.pop_next()
        if item is None:
            return
        self._render_queue()
        self.write(f"\n> {item['text']}\n", "user")
        self._process_async(item["text"], web=item["web"])

    def _cancel_queued(self, qid):
        self._queue.cancel(qid)
        self._render_queue()

    def _render_queue(self):
        """Muted chips above the input row: 'Queued (n):' then each prompt with [x]."""
        for w in self.queue_strip.winfo_children():
            w.destroy()
        items = self._queue.items()
        if not items:
            self.queue_strip.grid_remove()
            return
        tk.Label(self.queue_strip, text=f"Queued ({len(items)}):", bg=COLOR_BG, fg=MUTED,
                 font=FONT_UI).pack(side=tk.LEFT, padx=(0, PAD_S))
        shown = items[:3]  # ponytail: first 3 chips + a count; scroll if long queues matter
        for item in shown:
            chip = tk.Frame(self.queue_strip, bg=SURFACE, highlightthickness=1,
                            highlightbackground=BORDER)
            chip.pack(side=tk.LEFT, padx=(0, PAD_S))
            tk.Label(chip, text=queue_preview(item["text"]), bg=SURFACE, fg=MUTED,
                     font=FONT_SMALL).pack(side=tk.LEFT, padx=(PAD_S, 0))
            x = tk.Label(chip, text="[x]", bg=SURFACE, fg=MUTED, font=FONT_SMALL_MONO, cursor="hand2")
            x.pack(side=tk.LEFT, padx=PAD_S)
            x.bind("<Button-1>", lambda e, q=item["id"]: self._cancel_queued(q))
            x.bind("<Enter>", lambda e, w=x: w.config(fg=RED))
            x.bind("<Leave>", lambda e, w=x: w.config(fg=MUTED))
        if len(items) > len(shown):
            tk.Label(self.queue_strip, text=f"+{len(items) - len(shown)} more", bg=COLOR_BG,
                     fg=MUTED, font=FONT_SMALL).pack(side=tk.LEFT)
        self.queue_strip.grid()

    def handle_voice(self):
        # Allowed mid-reply: the words land in the input, and sending them
        # while busy queues them like typed text.
        if self._listening:
            return
        self._listening = True
        self.display_system_message("Listening for command...")
        threading.Thread(target=self._voice_thread, daemon=True).start()

    def _voice_thread(self):
        try:
            res = self.core.ears.listen(5) if self.core.ears else "[ERROR] Audio module missing."
        except Exception as e:
            res = f"[ERROR] Voice capture failed: {e}"
        self._listening = False
        if "[ERROR]" in res:
            self.display_system_message(res)
        else:
            self.ui_call(self.entry.insert, "1.0", res)

    def _process_async(self, data, web=False):
        self.is_processing = True
        self._set_send_mode(True)
        # Live streaming region: everything after this mark is redrawn as the
        # answer arrives, then replaced by the fully rendered reply in _finish.
        self.chat.mark_set("stream_start", "end-1c")
        self.chat.mark_gravity("stream_start", tk.LEFT)
        # shown: visible text currently drawn (None = nothing, or the
        # "reasoning..." placeholder, which any real text fully replaces).
        pending = {"text": None, "streamed": False, "shown": None, "placeholder": False}
        self._stream_state = pending

        def on_delta(visible):
            # Called from the worker thread; coalesce so a burst of tokens
            # costs one redraw on the Tk thread, not one per token.
            first = pending["text"] is None
            pending["text"] = visible
            if first:
                self.ui_call(self._flush_stream, pending)

        def on_tool(name, status, error=None):
            self.ui_call(self._add_tool_chip, name, status, error)

        def on_notice(text):
            # Shown by _finish, after the reply: a line written now would land
            # inside the stream region and be wiped with it.
            pending["notice"] = text

        def on_final(meta):
            # Read by _finish: the model's thinking, and whether STOP cut it short.
            pending["reasoning"] = meta.get("reasoning") or ""
            pending["cancelled"] = bool(meta.get("cancelled"))

        def task():
            try:
                resp = self.core.respond_to_input(data, on_delta=on_delta, on_tool=on_tool, web=web,
                                                  on_notice=on_notice, on_final=on_final)
            except Exception as e:
                resp = f"[SYSTEM FAILURE] {e}"
            self.ui_call(self._finish, resp)
        threading.Thread(target=task, daemon=True).start()

    def _at_bottom(self):
        return self.chat.yview()[1] >= 0.999

    def _flush_stream(self, pending):
        text, pending["text"] = pending["text"], None
        if text is None or not self.is_processing:
            return
        pending["streamed"] = True
        if text:
            mode, chunk = _stream_suffix(pending["shown"], text)
            if mode == "append" and not chunk:
                return
        elif pending["placeholder"]:
            return
        else:
            mode, chunk = "replace", ""

        follow = self._at_bottom()
        self.chat.config(state=tk.NORMAL)
        if mode == "append":
            # Append-only: redrawing the whole reply per flush was O(n^2).
            self.chat.insert(tk.END, chunk, "ai")
        else:
            # "end-1c", not END: when the region is empty Tk would otherwise
            # delete the newline *before* the mark (the user line's, or a
            # tool chip's), gluing the reply onto the previous line.
            self.chat.delete("stream_start", "end-1c")
            if text:
                self.chat.insert(tk.END, "\n" + text, "ai")
            else:
                self.chat.insert(tk.END, "\n>> reasoning...", "system")
        self.chat.config(state=tk.DISABLED)
        pending["shown"] = text or None
        pending["placeholder"] = not text
        if follow:
            self.chat.see(tk.END)

    def _add_tool_chip(self, name, status, error=None):
        """One dim line per tool call, kept *above* the live stream region.

        Inserted at stream_start, which then moves past the chip: the streamed
        answer still appends after it, and the replace/_finish deletes (which
        start at stream_start) never remove a chip.
        """
        state = self._stream_state
        if not self.is_processing or state is None:
            return
        chips = state.setdefault("chips", {})  # tool name -> mark at its line end
        follow = self._at_bottom()
        self.chat.config(state=tk.NORMAL)
        if status == "start" or name not in chips:
            line = f"  [tool] {name} ...\n"
            mark = f"tool_chip_{state.setdefault('chip_seq', 0)}"
            state["chip_seq"] += 1
            self.chat.insert("stream_start", line, "tool")
            self.chat.mark_set(mark, f"stream_start + {len(line) - 1} chars")
            self.chat.mark_set("stream_start", f"stream_start + {len(line)} chars")
            chips[name] = mark
        if status != "start":
            mark = chips.pop(name)
            self.chat.insert(mark, " ok" if status == "ok" else f" error: {error or 'failed'}", "tool")
            self.chat.mark_unset(mark)
        self.chat.config(state=tk.DISABLED)
        if follow:
            self.chat.see(tk.END)

    # --- MARKDOWN RENDERING PIPELINE ---
    def _finish(self, r):
        """End of every reply (answer, STOP, or error): render it, then send the next queued."""
        self.is_processing = False
        self._set_send_mode(False)
        state = getattr(self, "_stream_state", None)
        if state and state["streamed"]:
            # Drop the live preview; the full render below replaces it. Only
            # when a stream actually drew, so command output (ingest, status)
            # written during processing is never wiped.
            self.chat.config(state=tk.NORMAL)
            self.chat.delete("stream_start", "end-1c")  # see _flush_stream
            self.chat.config(state=tk.DISABLED)
        state = state or {}
        self._parse_and_write_ai(r, reasoning=state.get("reasoning", ""),
                                 cancelled=state.get("cancelled", False))
        if state.get("notice"):
            # Written now, not via ui_call: it must land before the next queued prompt.
            self.write(f"\n>> {state['notice']}\n", "system")
        self._start_next_queued()

    def _copy_to_clipboard(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.display_system_message("Code copied to clipboard.")

    def _insert_toggle(self, title, body):
        """A collapsed '[+] title' line in the chat that expands to body, muted and small."""
        self.chat.insert(tk.END, "\n")
        frame = tk.Frame(self.chat, bg=COLOR_BG)
        content = tk.Frame(frame, bg=COLOR_BG)
        tk.Label(content, text=body, justify=tk.LEFT, bg=COLOR_BG, fg=MUTED, font=FONT_SMALL,
                 anchor="w", wraplength=max(300, self.chat.winfo_width() - PAD_L * 4)
                 ).pack(fill=tk.BOTH, padx=2, pady=0)
        # A flat Label as a link, not a bulky Button.
        head = tk.Label(frame, text=f"[+] {title}", bg=COLOR_BG, fg=MUTED, font=FONT_SMALL,
                        cursor="hand2", anchor="w")

        def toggle(event=None):
            if content.winfo_manager():
                content.pack_forget()
                head.config(text=f"[+] {title}")
            else:
                content.pack(fill=tk.X, pady=(2, 0))
                head.config(text=f"[-] {title}")
        head.bind("<Button-1>", toggle)
        head.toggle = toggle  # for tests: a withdrawn window gets no clicks
        head.pack(fill=tk.X)
        self.chat.window_create(tk.END, window=frame)
        self.chat.insert(tk.END, "\n\n")
        return head

    def _parse_and_write_ai(self, text, reasoning="", cancelled=False):
        follow = self._at_bottom()
        self.chat.config(state=tk.NORMAL)
        
        # Dual-Phase Data Extraction Protocol
        analysis_text = ""
        main_text = text

        if "[ANALYSIS]" in main_text:
            parts = main_text.split("[KERNEL_RESPONSE]")
            if len(parts) > 1:
                analysis_text = parts[0].replace("[ANALYSIS]", "").strip()
                main_text = parts[1].strip()
            else:
                analysis_text = parts[0].replace("[ANALYSIS]", "").strip()
                main_text = ""
        else:
            main_text = main_text.replace("[KERNEL_RESPONSE]", "").strip()

        # Never render a blank turn. A response that parses to nothing used to
        # leave the chat pane silently unchanged, which read as "the app did
        # not respond" and hid the real fault completely.
        # (A STOPped reply may legitimately have no text yet.)
        if not main_text.strip() and not cancelled:
            main_text = ("[KERNEL FAULT] Empty response body. "
                         "See RAW_OUTPUT in logs/ghost_audit.log.")

        # Collapsed dropdowns: a thinking model's reasoning (server field), and
        # the [ANALYSIS] block that non-thinking models write inline.
        if reasoning and reasoning.strip():
            self._insert_toggle("reasoning", reasoning.strip())
        if analysis_text:
            self._insert_toggle("trace_cognition", analysis_text)

        # Core Text Rendering and Code Block Mapping
        blocks = main_text.split("```")
        
        for i, block in enumerate(blocks):
            if i % 2 == 0:
                if block:
                    self.chat.insert(tk.END, block, "ai")
            else:
                lines = block.split('\n', 1)
                lang = lines[0].strip() if len(lines) > 1 else ""
                code_content = lines[1] if len(lines) > 1 else block
                code_content = code_content.strip()
                
                if code_content:
                    self.chat.insert(tk.END, "\n")
                    
                    h_frame = tk.Frame(self.chat, bg=SURFACE_2, padx=PAD, pady=2)
                    tk.Label(
                        h_frame, text=lang.upper() if lang else "CODE",
                        bg=SURFACE_2, fg=MUTED, font=FONT_SMALL_MONO
                    ).pack(side=tk.LEFT)

                    btn = tk.Button(
                        h_frame, text="[COPY]", bg=SURFACE_2, fg=MUTED, font=FONT_SMALL_MONO,
                        command=lambda c=code_content: self._copy_to_clipboard(c)
                    )
                    btn.pack(side=tk.RIGHT)
                    
                    self.chat.window_create(tk.END, window=h_frame)
                    self.chat.insert(tk.END, "\n")
                    self.chat.insert(tk.END, code_content + "\n", "code_block")
                    self.chat.insert(tk.END, "\n")

        if cancelled:
            self.chat.insert(tk.END, " (stopped)", "stopped")
        self.chat.insert(tk.END, "\n", "ai")
        self.chat.config(state=tk.DISABLED)
        if follow:
            self.chat.see(tk.END)

    def write(self, t, tag):
        # Only follow the output if the reader is already at the bottom;
        # never yank them back down while they are reading scrollback.
        follow = self._at_bottom()
        self.chat.config(state=tk.NORMAL)
        self.chat.insert(tk.END, t, tag)
        self.chat.config(state=tk.DISABLED)
        if follow:
            self.chat.see(tk.END)

    def clear_chat(self):
        """Empty the chat pane. Tk thread only; workers use ui_call(ui.clear_chat)."""
        self.chat.config(state=tk.NORMAL)
        self.chat.delete("1.0", tk.END)
        self.chat.config(state=tk.DISABLED)

    def display_system_message(self, m):
        """Thread-safe: callable from any thread."""
        m = str(m).removeprefix(">>").lstrip()  # some callers pre-prefix; avoid ">> >>"
        self.ui_call(self.write, f"\n>> {m}\n", "system")

    # --- WORKER -> TK HANDOFF ---
    def ui_call(self, fn, *args):
        """Run fn(*args) on the Tk thread. Safe from any thread (queue.Queue)."""
        if threading.current_thread() is threading.main_thread():
            self.root.after(0, fn, *args)  # already on Tk: skip the pump latency
        else:
            self._ui_queue.put((fn, args))

    def _pump_ui_queue(self):
        """The single main-thread consumer of ui_call(); re-arms itself."""
        while True:
            try:
                fn, args = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                fn(*args)
            except Exception as e:
                print(f"[UI] Deferred UI update failed: {e}")
        # Tight while a reply streams so tokens appear smoothly; relaxed when
        # idle, where only telemetry and system messages arrive.
        self.root.after(33 if self.is_processing else 250, self._pump_ui_queue)

    def print_logo(self):
        self.write(ASCII_LOGO, "logo")
        self.write(f"\n{VERSION_TEXT}\n\n", "logo")

    # --- TELEMETRY & HARDWARE MONITORING ---
    def _toggle_research(self):
        """POST off the Tk thread; the button only flips once the server took it."""
        want = not self.research_active
        endpoint = "/research/enable" if want else "/research/disable"

        def task():
            try:
                requests.post(SERVER_URL + endpoint, headers=HEADERS, timeout=1)
            except Exception:
                self.display_system_message("Failed to toggle Research Cluster. Run FAH Client and then try again.")
                return
            self.ui_call(self._set_research_state, want)
        threading.Thread(target=task, daemon=True).start()

    def _set_research_state(self, active):
        self.research_active = active
        self.btn_research.config(text=f"RESEARCH: {'ON' if active else 'OFF'}", fg=LIME if active else MINT)

    def _read_telemetry(self):
        """Worker thread only: gather every reading into a plain dict. No Tk here."""
        snap = {"cpu": None, "ram": None, "vram": None,
                "research": None, "stability": None, "offline": False}
        try:
            snap["cpu"] = psutil.cpu_percent()
            snap["ram"] = psutil.virtual_memory().percent
        except Exception:
            pass

        # NVML, initialised once (nvidia-smi used to be spawned per poll at
        # ~1.7s a call). No NVIDIA GPU / driver: stop trying; only the VRAM
        # bar stays empty.
        if self._nvml_handle is None:
            try:
                import pynvml
                pynvml.nvmlInit()
                self._nvml_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            except Exception:
                self._nvml_handle = False
        if self._nvml_handle:
            try:
                import pynvml
                mem = pynvml.nvmlDeviceGetMemoryInfo(self._nvml_handle)
                snap["vram"] = mem.used / mem.total * 100
            except Exception:
                pass

        # Backend telemetry is independent of the hardware reads above, so a
        # CPU-only box (GPU_LAYERS=0) still gets FSM/health/latency/panics.
        try:
            r = requests.get(SERVER_URL + "/research/status", headers=HEADERS, timeout=0.5)
            if r.status_code == 200:
                snap["research"] = r.json()
            r = requests.get(SERVER_URL + "/telemetry/stability", headers=HEADERS, timeout=0.5)
            if r.status_code == 200:
                snap["stability"] = r.json()
        except Exception:
            snap["offline"] = True
        return snap

    def _telemetry_worker(self):
        """One long-lived poller; results reach Tk only through ui_call."""
        while True:
            try:
                self.ui_call(self._apply_telemetry, self._read_telemetry())
            except Exception as e:
                print(f"[UI] Telemetry poll failed: {e}")
            time.sleep(1.5)

    def _apply_telemetry(self, snap):
        """Tk thread: the only place telemetry touches widgets."""
        for bar, key in ((self.bar_cpu, "cpu"), (self.bar_ram, "ram"), (self.bar_vram, "vram")):
            if snap[key] is not None:
                bar.update_value(snap[key])

        research = snap["research"]
        if research is not None:
            active = research.get('active')
            state = "FAH_ACTIVE (IDLE)" if active else "INFERENCE / STANDBY"
            self.lbl_status.config(text=f"FSM: {state}", fg=AMBER if active else COLOR_ACCENT)

        if snap["offline"]:
            for lbl, text in ((self.lbl_fsm_state, "OFFLINE"), (self.lbl_health_score, "0%"),
                              (self.lbl_avg_latency, "0ms"), (self.lbl_panic_count, "0")):
                lbl.config(text=text, fg=COLOR_ERROR)
            return

        data = snap["stability"]
        if data is not None:
            metrics = data.get('metrics', {})
            panic_count = metrics.get('panics_triggered', 0)
            self.lbl_fsm_state.config(
                text=data.get('current_fsm_state', 'UNKNOWN').replace('_', ' ').title(), fg=COLOR_ACCENT)
            self.lbl_health_score.config(text=data.get('hardware_reliability_score', '0%'), fg=COLOR_ACCENT)
            self.lbl_avg_latency.config(text=f"{metrics.get('average_handoff_latency_ms', 0)}ms", fg=COLOR_ACCENT)
            self.lbl_panic_count.config(text=str(panic_count),
                                        fg=COLOR_ERROR if panic_count > 0 else COLOR_ACCENT)

    def run(self):
        self.print_logo()
        self._refresh_session_list()
        self._pump_ui_queue()
        self._load_settings()  # WEB button / SEARCH state from the server
        self._refresh_active_model()
        threading.Thread(target=self._telemetry_worker, daemon=True).start()
        if SPELLCHECK_AVAILABLE:
            # After the window is up: the dictionary load is the slowest part
            # of startup and spellcheck is not needed for the first keystroke.
            self.root.after(500, self._load_spellchecker)
        threading.Thread(target=self.core.start, daemon=True).start()
        self.root.mainloop()

    def _on_closing(self):
        self.root.destroy()
        os._exit(0)