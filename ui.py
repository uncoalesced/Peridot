# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | INTERFACE & TELEMETRY OVERHAUL
# Copyright (C) 2026 uncoalesced
# 
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import tkinter as tk
from tkinter import font, ttk, messagebox, simpledialog
from PIL import Image, ImageTk
import threading
import psutil
import time
import subprocess
import os
import ctypes
import requests
import re
import webbrowser
from datetime import datetime
from pathlib import Path

from config import SERVER_HOST, SERVER_PORT, API_KEY, MODEL_PATH, TOTAL_VRAM_GB

# --- UK ENGLISH DICTIONARY ENGINE ---
try:
    from spellchecker import SpellChecker
    SPELLCHECK_AVAILABLE = True
except ImportError:
    SPELLCHECK_AVAILABLE = False
    print("[WARN] pyspellchecker module missing. Run: pip install pyspellchecker")

# --- OS-LEVEL OVERRIDES ---
try:
    # High DPI Awareness
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
    # Taskbar Icon Separation
    myappid = 'uncoalesced.peridot.sovereign.1_5'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass

# --- THEME & CONFIGURATION ---
COLOR_BG = "#050505"
COLOR_TEXT = "#E0E0E0"
COLOR_ACCENT = "#00FF41"
COLOR_DIM = "#1A1A1A"
COLOR_USER = "#A48EFF"
COLOR_AI = "#E0E0E0"
COLOR_SYSTEM = "#00FF41"
COLOR_ERROR = "#FF2A6D"
COLOR_INPUT = "#0F0F0F"
COLOR_CODE_BG = "#0C0C0C"

FONT_MAIN = ("Consolas", 12)
FONT_BOLD = ("Consolas", 12, "bold")
FONT_CODE = ("Consolas", 12)
FONT_UI = ("Consolas", 9, "bold")
FONT_LINK = ("Consolas", 9, "bold underline")

SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

# --- ASCII LOGO ---
ASCII_LOGO = """
██████╗ ███████╗██████╗ ██╗██████╗  ██████╗ ████████╗
██╔══██╗██╔════╝██╔══██╗██║██╔══██╗██╔═══██╗╚══██╔══╝
██████╔╝█████╗  ██████╔╝██║██║  ██║██║   ██║   ██║   
██╔═══╝ ██╔══╝  ██╔══██╗██║██║  ██║██║   ██║   ██║   
██║     ███████╗██║  ██║██║██████╔╝╚██████╔╝   ██║   
╚═╝     ╚══════╝╚═╝  ╚═╝╚═╝╚═════╝  ╚═════╝    ╚═╝   
"""
VERSION_TEXT = "SOVEREIGN KERNEL v1.5.2 [STABLE]\nENGINEERED BY UNCOALESCED"


class TechProgressBar(tk.Canvas):
    def __init__(self, parent, width=100, height=18, bg=COLOR_DIM):
        super().__init__(
            parent, width=width, height=height, bg=bg, highlightthickness=0
        )
        self.w, self.h = width, height
        self.rect = self.create_rectangle(0, 0, 0, height, fill=COLOR_ACCENT, width=0)
        self.text_shadow = self.create_text(
            width / 2 + 1, height / 2 + 1, text="0%", fill="#000000", font=("Consolas", 8, "bold")
        )
        self.text_main = self.create_text(
            width / 2, height / 2, text="0%", fill="#FFFFFF", font=("Consolas", 8, "bold")
        )

    def update_value(self, percent):
        percent = max(0, min(100, percent))
        col = (
            "#00FF41" if percent <= 60
            else ("#FFD700" if percent <= 85 else "#FF8C00" if percent <= 95 else "#FF2A6D")
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
        
        # Session State
        self.sessions = []
        self._current_session_menu_index = None

        # Kinetic Scroll State Variables
        self.chat_scroll_velocity = 0.0
        self.chat_scroll_animating = False
        
        if SPELLCHECK_AVAILABLE:
            self.spell = SpellChecker(language='en')
            self.system_words = {"python", "fastapi", "sqlalchemy", "pydantic", "sqlite", "vram", "peridot"}
            
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
            
            self.spell.word_frequency.remove_words(us_variants)
            self.spell.word_frequency.load_words(uk_variants + list(self.system_words))
        
        self._setup_main_window()
        self._configure_notebook_styles()
        self._create_widgets()
        self._configure_styles()
        self._bind_shortcuts()
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _setup_main_window(self):
        self.root.title("Peridot | Sovereign OS")
        self.root.geometry("1150x800")
        self.root.configure(bg=COLOR_BG)
        
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.join(base_dir, "assets", "ui", "logo", "peridot.ico")
            self.root.iconbitmap(icon_path)
            
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if hwnd:
                hicon = ctypes.windll.user32.LoadImageW(0, icon_path, 1, 0, 0, 0x00000010 | 0x00000020)
                ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, hicon)
                ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, hicon)
        except Exception:
            pass

        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(2)), 4)
        except:
            pass

    def _configure_notebook_styles(self):
        """Injects custom terminal aesthetics into the tab engine and Comboboxes."""
        style = ttk.Style()
        style.theme_use("clam")
        
        # Notebook Tab Styling (Overriding light/dark colors kills the white outline)
        style.configure("TNotebook", background=COLOR_BG, borderwidth=0, lightcolor=COLOR_BG, darkcolor=COLOR_BG)
        style.configure("TNotebook.Tab", background=COLOR_DIM, foreground="#888888", font=FONT_UI, padding=[15, 5], borderwidth=0, lightcolor=COLOR_BG, darkcolor=COLOR_BG)
        style.map("TNotebook.Tab", background=[("selected", COLOR_INPUT)], foreground=[("selected", COLOR_ACCENT)])

        # Modern Deep-Theme Combobox Styling
        style.configure("TCombobox",
            fieldbackground=COLOR_INPUT,
            background=COLOR_DIM,
            foreground=COLOR_TEXT,
            bordercolor=COLOR_DIM,
            arrowcolor=COLOR_ACCENT,
            darkcolor=COLOR_DIM,
            lightcolor=COLOR_DIM
        )
        style.map("TCombobox",
            fieldbackground=[("readonly", COLOR_INPUT)],
            selectbackground=[("readonly", COLOR_DIM)],
            selectforeground=[("readonly", COLOR_ACCENT)]
        )
        
        # Dropdown Popup List Styling
        self.root.option_add('*TCombobox*Listbox.background', COLOR_INPUT)
        self.root.option_add('*TCombobox*Listbox.foreground', COLOR_TEXT)
        self.root.option_add('*TCombobox*Listbox.selectBackground', COLOR_DIM)
        self.root.option_add('*TCombobox*Listbox.selectForeground', COLOR_ACCENT)
        self.root.option_add('*TCombobox*Listbox.font', FONT_CODE)

        # Dark-themed Scrollbar (rejects native Win32 white artifacts entirely)
        style.configure("Vertical.TScrollbar",
            background=COLOR_DIM,
            troughcolor=COLOR_BG,
            bordercolor=COLOR_BG,
            arrowcolor=COLOR_ACCENT,
            lightcolor=COLOR_DIM,
            darkcolor=COLOR_DIM,
            gripcount=0
        )
        style.map("Vertical.TScrollbar",
            background=[("active", "#2A2A2A")],
            arrowcolor=[("active", "#FFFFFF")]
        )

    def _create_widgets(self):
        # Search Bar Overlay (Hidden by default)
        self.search_frame = tk.Frame(self.root, bg=COLOR_DIM, height=30)
        self.search_entry = tk.Entry(self.search_frame, bg=COLOR_INPUT, fg=COLOR_TEXT, font=FONT_UI, insertbackground=COLOR_ACCENT, relief=tk.FLAT)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10, pady=5)
        self.search_entry.bind("<KeyRelease>", self._execute_search)
        self.search_entry.bind("<Return>", self._execute_search)
        self.search_entry.bind("<Escape>", self._close_search)
        btn_close_search = tk.Button(self.search_frame, text="[X]", bg=COLOR_DIM, fg=COLOR_ERROR, font=FONT_UI, command=self._close_search, relief=tk.FLAT, cursor="hand2")
        btn_close_search.pack(side=tk.RIGHT, padx=10)

        # Notebook Layout Manager Partition
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=(20, 10))

        # Tab 1: Chat Buffer Matrix (PanedWindow with session sidebar)
        self.tab_chat = tk.Frame(self.notebook, bg=COLOR_BG)
        self.notebook.add(self.tab_chat, text="[01] CHAT MATRIX")

        # Toggle button row above chat pane
        self.chat_toolbar = tk.Frame(self.tab_chat, bg=COLOR_BG, height=28)
        self.chat_toolbar.pack(fill=tk.X, before=None)
        self.chat_toolbar.pack_propagate(False)

        self.btn_toggle_sessions = tk.Button(self.chat_toolbar, text="[>] SESSIONS",
                                              bg=COLOR_DIM, fg=COLOR_ACCENT,
                                              font=FONT_UI, relief=tk.FLAT,
                                              cursor="hand2",
                                              command=self._toggle_session_drawer)
        self.btn_toggle_sessions.pack(side=tk.LEFT, padx=(5, 0))

        # Re-enforced resizable PanedWindow
        self.chat_pane = tk.PanedWindow(self.tab_chat, orient=tk.HORIZONTAL,
                                         sashrelief=tk.RAISED, sashwidth=6, sashcursor="sb_h_double_arrow", bg=COLOR_BG, bd=0)
        self.chat_pane.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        # Left pane: Session sidebar (hidden by default, managed via toggle)
        self.session_frame = tk.Frame(self.chat_pane, bg=COLOR_BG, width=250)
        self.session_header = tk.Label(self.session_frame, text="SESSIONS",
                                        bg=COLOR_BG, fg=COLOR_ACCENT, font=FONT_UI, anchor="w")
        self.session_header.pack(fill=tk.X, padx=5, pady=(5, 2))

        self.btn_new_session = tk.Button(self.session_frame, text="[+] NEW SESSION",
                                          bg=COLOR_DIM, fg=COLOR_TEXT, font=FONT_UI,
                                          relief=tk.FLAT, cursor="hand2",
                                          command=self._new_session)
        self.btn_new_session.pack(fill=tk.X, padx=5, pady=(0, 5))

        session_scroll_frame = tk.Frame(self.session_frame, bg=COLOR_BG)
        session_scroll_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        self.session_listbox = tk.Listbox(
            session_scroll_frame, bg=COLOR_INPUT, fg=COLOR_TEXT,
            font=FONT_CODE, relief=tk.FLAT, highlightthickness=0,
            selectbackground=COLOR_DIM, selectforeground=COLOR_ACCENT,
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
        self.session_menu = tk.Menu(self.tab_chat, tearoff=0, bg=COLOR_DIM,
                                     fg=COLOR_TEXT, activebackground=COLOR_ACCENT,
                                     activeforeground="black", font=FONT_UI)
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
            highlightthickness=0, padx=10, pady=10, state=tk.DISABLED
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
        self.notebook.add(self.tab_vault, text="[02] KERNEL VAULT")

        self.vault_label = tk.Label(self.tab_vault, text=">> DATA-INGEST SECURE CONSOLE VECTOR DIRECTORY:", bg=COLOR_BG, fg=COLOR_ACCENT, font=FONT_UI, anchor="w")
        self.vault_label.pack(fill=tk.X, padx=15, pady=(15, 5))

        self.vault_list = tk.Listbox(
            self.tab_vault, bg=COLOR_INPUT, fg=COLOR_TEXT, font=FONT_CODE, 
            relief=tk.FLAT, highlightthickness=1, highlightcolor=COLOR_DIM, highlightbackground=COLOR_DIM,
            selectbackground=COLOR_DIM, selectforeground=COLOR_ACCENT
        )
        self.vault_list.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        # Tab 3: Settings & Hardware Configuration
        self.tab_settings = tk.Frame(self.notebook, bg=COLOR_BG)
        self.notebook.add(self.tab_settings, text="[03] SETTINGS")
        self._build_settings_tab()

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # Responsive Input Controls Layout
        self.in_frame = tk.Frame(self.root, bg=COLOR_BG)
        self.in_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        tk.Frame(self.in_frame, bg=COLOR_ACCENT, height=2).grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 10))
        
        self.in_frame.columnconfigure(0, weight=1) 
        self.in_frame.columnconfigure(1, weight=0) 
        self.in_frame.columnconfigure(2, weight=0) 

        self.entry = tk.Text(
            self.in_frame, bg=COLOR_INPUT, fg="white", font=FONT_MAIN,
            insertbackground=COLOR_ACCENT, relief=tk.FLAT, bd=5, height=1, width=1, wrap=tk.WORD, undo=False
        )
        self.entry.grid(row=1, column=0, sticky="ew", ipady=5)
        
        self.entry.bind("<Return>", self._on_enter)
        self.entry.bind("<Shift-Return>", self._on_shift_enter)
        self.entry.bind("<KeyRelease>", self._on_key_release)
        self.entry.bind("<Button-3>", self._show_spellcheck_menu)

        mic_img_path = os.path.join(os.path.dirname(__file__), "assets", "icons", "peridot_mic.ico")
        if os.path.exists(mic_img_path):
            mic_img = Image.open(mic_img_path).resize((24, 24), Image.LANCZOS)
            self.mic_photo = ImageTk.PhotoImage(mic_img)
            self.btn_mic = tk.Button(
                self.in_frame, image=self.mic_photo, command=self.handle_voice, bg=COLOR_DIM,
                relief=tk.FLAT, padx=10, pady=5, cursor="hand2"
            )
        else:
            self.btn_mic = tk.Button(
                self.in_frame, text="MIC", command=self.handle_voice, bg=COLOR_DIM, fg="white",
                font=("Consolas", 10, "bold"), relief=tk.FLAT, padx=15, pady=5, cursor="hand2"
            )
        self.btn_mic.grid(row=1, column=1, padx=(10, 5), sticky="ns")

        send_img_path = os.path.join(os.path.dirname(__file__), "assets", "icons", "peridot_send.ico")
        if os.path.exists(send_img_path):
            send_img = Image.open(send_img_path).resize((36, 24), Image.LANCZOS)
            self.run_photo = ImageTk.PhotoImage(send_img)
            self.btn_run = tk.Button(
                self.in_frame, image=self.run_photo, command=self.handle_input, bg=COLOR_ACCENT,
                relief=tk.FLAT, padx=10, pady=5, cursor="hand2"
            )
        else:
            self.btn_run = tk.Button(
                self.in_frame, text="EXECUTE", command=self.handle_input, bg=COLOR_ACCENT, fg="black",
                font=("Consolas", 10, "bold"), relief=tk.FLAT, padx=15, pady=5, cursor="hand2"
            )
        self.btn_run.grid(row=1, column=2, padx=5, sticky="ns")

        # Fixed Status Telemetry Panel
        self.stat_bar = tk.Frame(self.root, bg="#0A0A0A", height=40)
        self.stat_bar.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.lbl_status = tk.Label(self.stat_bar, text="FSM: CONNECTING", bg="#0A0A0A", fg="#666", font=FONT_UI)
        self.lbl_status.pack(side=tk.LEFT, padx=15)
        
        self.btn_research = tk.Button(
            self.stat_bar, text="RESEARCH: OFF", bg="#1A1A1A", fg="white", font=FONT_UI,
            relief=tk.FLAT, command=self._toggle_research, cursor="hand2"
        )
        self.btn_research.pack(side=tk.LEFT, padx=10)

        for m in [("RAM", "bar_ram"), ("CPU", "bar_cpu"), ("VRAM", "bar_vram")]:
            self._add_monitor(m[0], m[1])

    def _build_settings_tab(self):
        """Constructs hardware-aware configuration matrix."""
        # Top Config Container
        config_frame = tk.Frame(self.tab_settings, bg=COLOR_BG)
        config_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(config_frame, text=">> CURRENT ACTIVE MODEL:", bg=COLOR_BG, fg=COLOR_ACCENT, font=FONT_UI, anchor="w").pack(fill=tk.X, pady=(0, 5))
        
        try:
            current_model = os.path.basename(str(MODEL_PATH))
        except Exception:
            current_model = "UNKNOWN"

        self.lbl_current_model = tk.Label(config_frame, text=f"   {current_model}", bg=COLOR_BG, fg=COLOR_TEXT, font=FONT_MAIN, anchor="w")
        self.lbl_current_model.pack(fill=tk.X, pady=(0, 20))

        tk.Label(config_frame, text=">> HARDWARE-AWARE MODEL SWAP (E:\\Peridot\\models):", bg=COLOR_BG, fg=COLOR_ACCENT, font=FONT_UI, anchor="w").pack(fill=tk.X, pady=(0, 5))

        self.model_var = tk.StringVar()
        self.model_dropdown = ttk.Combobox(
            config_frame, textvariable=self.model_var, state="readonly", font=FONT_CODE
        )
        self.model_dropdown.pack(fill=tk.X, pady=(0, 10))

        # Use dynamic VRAM detection from config (Phase 2: Hardware Auto-Scaling)
        total_vram_gb = TOTAL_VRAM_GB if TOTAL_VRAM_GB > 0 else 8.0

        models_dir = r"E:\Peridot\models"
        self.available_models_map = {}
        dropdown_values = []

        if os.path.exists(models_dir):
            for f in os.listdir(models_dir):
                if f.endswith(".gguf") or f.endswith(".safetensors"):
                    file_size_gb = os.path.getsize(os.path.join(models_dir, f)) / (1024**3)
                    
                    if file_size_gb < (total_vram_gb * 0.6):
                        rating = "[HIGH COMPATIBILITY]"
                    elif file_size_gb < (total_vram_gb * 0.9):
                        rating = "[MEDIUM COMPATIBILITY]"
                    else:
                        rating = "[LOW COMPATIBILITY / OVERLOAD RISK]"
                    
                    display_str = f"{rating.ljust(35)} : {f}"
                    self.available_models_map[display_str] = f
                    dropdown_values.append(display_str)
                    
            self.model_dropdown['values'] = dropdown_values
            if dropdown_values:
                self.model_dropdown.current(0)
        else:
            self.model_dropdown['values'] = [" [ERROR] E:\\Peridot\\models directory not found."]
            self.model_dropdown.current(0)

        btn_swap = tk.Button(
            config_frame, text="APPLY WEIGHTS AND REBOOT KERNEL", bg=COLOR_DIM, fg=COLOR_TEXT,
            font=FONT_UI, relief=tk.FLAT, cursor="hand2", command=self._swap_model
        )
        btn_swap.pack(anchor="w", pady=(0, 20))

        tk.Frame(config_frame, bg=COLOR_DIM, height=1).pack(fill=tk.X, pady=(0, 20))
        
        tk.Label(config_frame, text=">> HARDWARE MEMORY MANAGEMENT:", bg=COLOR_BG, fg=COLOR_ACCENT, font=FONT_UI, anchor="w").pack(fill=tk.X, pady=(0, 5))
        
        btn_reclaim = tk.Button(
            config_frame, text="FORCE-RECLAIM VRAM", bg=COLOR_DIM, fg=COLOR_ERROR,
            font=FONT_UI, relief=tk.FLAT, cursor="hand2", command=self._force_reclaim_vram
        )
        btn_reclaim.pack(anchor="w", pady=(0, 20))

        # Footer Navigation Links
        footer_frame = tk.Frame(self.tab_settings, bg=COLOR_BG)
        footer_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=20)
        tk.Frame(footer_frame, bg=COLOR_DIM, height=1).pack(fill=tk.X, pady=(0, 10))

        link_frame = tk.Frame(footer_frame, bg=COLOR_BG)
        link_frame.pack(anchor="center")

        links = [
            ("Report Bugs", "https://github.com/uncoalesced/Peridot/issues"),
            ("About Peridot", "https://github.com/uncoalesced/Peridot/wiki/The-Sovereign-Directive"),
            ("Contribute", "https://github.com/uncoalesced/Peridot/blob/main/CONTRIBUTING.md")
        ]

        for text, url in links:
            lbl = tk.Label(link_frame, text=f"[{text}]", bg=COLOR_BG, fg=COLOR_USER, font=FONT_LINK, cursor="hand2")
            lbl.pack(side=tk.LEFT, padx=15)
            lbl.bind("<Button-1>", lambda e, u=url: webbrowser.open_new(u))

    def _swap_model(self):
        """Modifies config.py architecture map to select a new binary."""
        selection_str = self.model_var.get()
        if not selection_str or "[ERROR]" in selection_str:
            messagebox.showwarning("Warning", "Select a valid model from the dropdown matrix to apply.")
            return
            
        selected_model = self.available_models_map.get(selection_str)
        if not selected_model:
            return
            
        new_path = f"E:/Peridot/models/{selected_model}"
        
        try:
            with open("config.py", "r") as f:
                content = f.read()
            
            new_content = re.sub(r'MODEL_PATH\s*=\s*(?:Path\()?[\'"].*?[\'"]\)?', f'MODEL_PATH = Path("{new_path}")', content)
            
            with open("config.py", "w") as f:
                f.write(new_content)
                
            messagebox.showinfo("Kernel Update", "Neural weights mapped. Shut down the engine and restart launcher.py to load the new architecture into VRAM.")
            self.lbl_current_model.config(text=f"   {selected_model}")
        except Exception as e:
            messagebox.showerror("Write Fault", f"Failed to rewrite config.py: {str(e)}")

    def _force_reclaim_vram(self):
        """Sends a signal to the engine to manually flush GC and VRAM."""
        try:
            resp = requests.post(f"{SERVER_URL}/vram/reclaim", headers=HEADERS, timeout=10)
            if resp.status_code == 200:
                self.display_system_message("HARDWARE | Manual VRAM reclaim triggered successfully.")
            else:
                self.display_system_message(f"HARDWARE | VRAM reclaim failed: {resp.text}")
        except Exception as e:
            self.display_system_message(f"HARDWARE | Could not reach neural engine: {e}")

    def _bind_shortcuts(self):
        """Global key bindings for UX navigation."""
        self.root.bind("<Control-Key-1>", lambda e: self.notebook.select(0))
        self.root.bind("<Control-Key-2>", lambda e: self.notebook.select(1))
        self.root.bind("<Control-Key-3>", lambda e: self.notebook.select(2))
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
            
        self.chat.tag_config("search", background="#FFD700", foreground="black")

    def _add_monitor(self, lbl, var):
        f = tk.Frame(self.stat_bar, bg="#0A0A0A")
        f.pack(side=tk.RIGHT, padx=15, pady=5)
        tk.Label(f, text=lbl, bg="#0A0A0A", fg=COLOR_ACCENT, font=("Consolas", 8)).pack(side=tk.LEFT, padx=(0, 5))
        b = TechProgressBar(f, width=90, height=18, bg="#1A1A1A")
        b.pack(side=tk.LEFT)
        setattr(self, var, b)

    def _configure_styles(self):
        for tag, col in [
            ("user", COLOR_USER),
            ("ai", COLOR_AI),
            ("system", COLOR_ACCENT),
            ("logo", COLOR_ACCENT),
        ]:
            self.chat.tag_config(tag, foreground=col, font=FONT_BOLD if tag != "ai" else FONT_MAIN)
        self.chat.tag_config("logo", justify="center", font=("Consolas", 11, "bold"))
        self.chat.tag_config("code_block", font=FONT_CODE, foreground="#FFD700", background=COLOR_CODE_BG, lmargin1=10, lmargin2=10, rmargin=10)
        
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
        """High-frequency (200Hz) animation loop for sub-pixel fluid text movement."""
        if abs(self.chat_scroll_velocity) < 1.0:
            self.chat_scroll_velocity = 0.0
            self.chat_scroll_animating = False
            return
            
        self.chat_scroll_animating = True
        
        step = self.chat_scroll_velocity * 0.15 
        pixel_step = int(step)
        if pixel_step == 0:
            pixel_step = 1 if step > 0 else -1
            
        try:
            self.chat.yview_scroll(pixel_step, "pixels")
        except:
            self.chat.yview_scroll(1 if pixel_step > 0 else -1, "units")
            self.chat_scroll_velocity = 0
            self.chat_scroll_animating = False
            return
            
        self.chat_scroll_velocity -= step
        self.root.after(5, self._animate_smooth_scroll)

    def _on_tab_changed(self, event):
        selected_tab = self.notebook.index(self.notebook.select())
        if selected_tab == 1:
            self._update_vault_directory()

    def _update_vault_directory(self):
        self.vault_list.delete(0, tk.END)
        
        vault_dir = os.path.join("input", "processed")
        fallback_dir = "input"
        
        if os.path.exists(vault_dir):
            files = [f for f in os.listdir(vault_dir) if os.path.isfile(os.path.join(vault_dir, f))]
            if not files:
                self.vault_list.insert(tk.END, " [EMPTY] No text corpora or source files detected inside archived sectors.")
            for file in files:
                self.vault_list.insert(tk.END, f" └── [SECURED-VAULT-NODE] : {file}")
        elif os.path.exists(fallback_dir):
            files = [f for f in os.listdir(fallback_dir) if os.path.isfile(os.path.join(fallback_dir, f))]
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
            self.chat.config(state=tk.NORMAL)
            self.chat.delete("1.0", tk.END)
            self.chat.config(state=tk.DISABLED)
            self.display_system_message(f"New session created.")
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
                self.chat.config(state=tk.NORMAL)
                self.chat.delete("1.0", tk.END)
                self.chat.config(state=tk.DISABLED)
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
            dialog.configure(bg="#000000")
            dialog.geometry("350x120")
            dialog.resizable(False, False)
            dialog.transient(self.root)
            dialog.grab_set()

            # Center relative to root window
            x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 175
            y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 60
            dialog.geometry(f"+{x}+{y}")

            lbl = tk.Label(dialog, text="[ ENTER NEW SESSION TITLE ]", font=("Courier", 10, "bold"), fg="#00FF00", bg="#000000")
            lbl.pack(pady=(15, 5))

            entry = tk.Entry(dialog, font=("Courier", 12), bg="#111111", fg="#00FF00", insertbackground="#00FF00", relief=tk.FLAT)
            entry.insert(0, current_title)
            entry.pack(fill=tk.X, padx=20, pady=5)
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
        self.chat.config(state=tk.NORMAL)
        self.chat.delete("1.0", tk.END)
        self.chat.config(state=tk.DISABLED)
        if not history:
            return
        for msg in history:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                self.write(f"\n> {content}\n", "user")
            elif role == "assistant":
                self._parse_and_write_ai(content)
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
                    display = f"{'●' if s['session_id'] == self.core.current_session_id else '○'} {title}"
                    self.session_listbox.insert(tk.END, display)
                    self.display_mapping.append(s)
        except Exception as e:
            print(f"[UI] Session list refresh failed: {e}")

    # --- SPELLCHECK ARBITRATION ---
    def _run_spellcheck(self):
        if not SPELLCHECK_AVAILABLE:
            return
            
        self.entry.tag_remove("misspelled", "1.0", tk.END)
        content = self.entry.get("1.0", "end-1c")
        
        words = re.finditer(r'\b[a-zA-Z]+\b', content)
        for match in words:
            word = match.group()
            if len(word) > 2:
                if word.lower() not in self.spell:
                    start_idx = f"1.0 + {match.start()} chars"
                    end_idx = f"1.0 + {match.end()} chars"
                    self.entry.tag_add("misspelled", start_idx, end_idx)

    def _apply_correction(self, start, end, correct_word):
        self.entry.delete(start, end)
        self.entry.insert(start, correct_word)
        self._run_spellcheck()

    def _show_spellcheck_menu(self, event):
        if not SPELLCHECK_AVAILABLE:
            return
            
        try:
            index = self.entry.index(f"@{event.x},{event.y}")
            tags = self.entry.tag_names(index)
            
            if "misspelled" in tags:
                menu = tk.Menu(self.root, tearoff=0, bg=COLOR_DIM, fg="white", activebackground=COLOR_ACCENT, activeforeground="black", font=FONT_UI)
                
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
        self.entry.update_idletasks()
        dl = self.entry.count("1.0", "end-1c", "displaylines")
        num_lines = (dl[0] if dl else 0) + 1
        new_height = min(max(1, num_lines), 8)
        self.entry.config(height=new_height)
        self.entry.see(tk.INSERT)

    def handle_input(self):
        if self.is_processing: return
        t = self.entry.get("1.0", tk.END).strip()
        if not t: return
        
        self.entry.delete("1.0", tk.END)
        self._adjust_input_height()
        self.entry.tag_remove("misspelled", "1.0", tk.END)
        
        self.write(f"\n> {t}\n", "user")
        self._process_async(t)

    def handle_voice(self):
        if self.is_processing: return
        self.display_system_message("Listening for command...")
        threading.Thread(target=self._voice_thread, daemon=True).start()

    def _voice_thread(self):
        res = self.core.ears.listen(5) if self.core.ears else "[ERROR] Audio module missing."
        self.root.after(0, lambda: self.entry.insert("1.0", res) if "[ERROR]" not in res else self.display_system_message(res))

    def _process_async(self, data):
        self.is_processing = True
        def task():
            try:
                resp = self.core.respond_to_input(data)
            except Exception as e:
                resp = f"[SYSTEM FAILURE] {e}"
            self.root.after(0, self._finish, resp)
        threading.Thread(target=task, daemon=True).start()

    # --- MARKDOWN RENDERING PIPELINE ---
    def _finish(self, r):
        self.is_processing = False
        self._parse_and_write_ai(r)

    def _copy_to_clipboard(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()
        self.display_system_message("Code copied to clipboard.")

    def _parse_and_write_ai(self, text):
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
            
        # Stealth UI Render: Cognitive Analysis Dropdown
        if analysis_text:
            self.chat.insert(tk.END, "\n")
            
            a_frame = tk.Frame(self.chat, bg=COLOR_BG)
            content_frame = tk.Frame(a_frame, bg=COLOR_BG)
            
            lbl = tk.Label(content_frame, text=analysis_text, justify=tk.LEFT,
                           bg=COLOR_BG, fg="#555555", font=("Consolas", 8), anchor="w")
            lbl.pack(fill=tk.BOTH, padx=2, pady=0)
            
            state = {"open": False}
            btn_text = tk.StringVar(value="[+] trace_cognition")
            
            def toggle_analysis(event=None, c_frame=content_frame, b_var=btn_text, s=state):
                if s["open"]:
                    c_frame.pack_forget()
                    b_var.set("[+] trace_cognition")
                    s["open"] = False
                else:
                    c_frame.pack(fill=tk.X, pady=(2, 0))
                    b_var.set("[-] trace_cognition")
                    s["open"] = True

            # Use a flat Label mapped as a hyperlink instead of a bulky Tkinter Button
            btn = tk.Label(a_frame, textvariable=btn_text, bg=COLOR_BG, fg="#555555",
                           font=("Consolas", 8, "italic"), cursor="hand2", anchor="w")
            btn.bind("<Button-1>", toggle_analysis)
            btn.pack(fill=tk.X)
            
            self.chat.window_create(tk.END, window=a_frame)
            self.chat.insert(tk.END, "\n\n")

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
                    
                    h_frame = tk.Frame(self.chat, bg="#1E1E1E", padx=8, pady=2)
                    tk.Label(
                        h_frame, text=lang.upper() if lang else "CODE", 
                        bg="#1E1E1E", fg="#888", font=("Consolas", 9, "bold")
                    ).pack(side=tk.LEFT)
                    
                    btn = tk.Button(
                        h_frame, text="[COPY]", bg="#1E1E1E", fg=COLOR_ACCENT, 
                        font=("Consolas", 9, "bold"), relief=tk.FLAT,
                        activebackground="#2A2A2A", activeforeground=COLOR_ACCENT,
                        command=lambda c=code_content: self._copy_to_clipboard(c), cursor="hand2"
                    )
                    btn.pack(side=tk.RIGHT)
                    
                    self.chat.window_create(tk.END, window=h_frame)
                    self.chat.insert(tk.END, "\n")
                    self.chat.insert(tk.END, code_content + "\n", "code_block")
                    self.chat.insert(tk.END, "\n")
        
        self.chat.insert(tk.END, "\n", "ai")
        self.chat.see(tk.END)
        self.chat.config(state=tk.DISABLED)

    def write(self, t, tag):
        self.chat.config(state=tk.NORMAL)
        self.chat.insert(tk.END, t, tag)
        self.chat.see(tk.END)
        self.chat.config(state=tk.DISABLED)

    def display_system_message(self, m):
        self.root.after(0, lambda: self.write(f"\n>> {m}\n", "system"))

    def print_logo(self):
        self.write(ASCII_LOGO, "logo")
        self.write(f"\n{VERSION_TEXT}\n\n", "logo")

    # --- TELEMETRY & HARDWARE MONITORING ---
    def _toggle_research(self):
        self.research_active = not self.research_active
        endpoint = "/research/enable" if self.research_active else "/research/disable"
        try:
            requests.post(SERVER_URL + endpoint, headers=HEADERS, timeout=1)
            state = "ON" if self.research_active else "OFF"
            color = COLOR_ACCENT if self.research_active else "white"
            self.btn_research.config(text=f"RESEARCH: {state}", fg=color)
        except Exception:
            self.display_system_message("Failed to toggle Research Cluster. Run FAH Client and then try again.")

    def _poll_backend_telemetry(self):
        try:
            r = requests.get(SERVER_URL + "/research/status", headers=HEADERS, timeout=0.5)
            if r.status_code == 200:
                data = r.json()
                state = "FAH_ACTIVE (IDLE)" if data.get('active') else "INFERENCE / STANDBY"
                color = "#FFD700" if data.get('active') else COLOR_ACCENT
                self.lbl_status.config(text=f"FSM: {state}", fg=color)
        except Exception:
            self.lbl_status.config(text="FSM: KERNEL UNREACHABLE", fg=COLOR_ERROR)

    def _update_stats(self):
        if not self.root.winfo_exists(): return
        try:
            self.bar_cpu.update_value(psutil.cpu_percent())
            self.bar_ram.update_value(psutil.virtual_memory().percent)
            
            c = ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"]
            o = subprocess.check_output(c, creationflags=0x08000000).decode().strip().split(",")
            self.bar_vram.update_value((int(o[0]) / int(o[1])) * 100)
            
            threading.Thread(target=self._poll_backend_telemetry, daemon=True).start()
        except:
            pass
        self.root.after(1500, self._update_stats)

    def run(self):
        self.print_logo()
        self._refresh_session_list()
        self._update_stats()
        threading.Thread(target=self.core.start, daemon=True).start()
        self.root.mainloop()

    def _on_closing(self):
        self.root.destroy()
        os._exit(0)