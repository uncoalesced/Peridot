# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | INTERFACE & TELEMETRY
# Copyright (C) 2026 uncoalesced
# 
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import tkinter as tk
from tkinter import scrolledtext, font
import threading
import psutil
import time
import subprocess
import os
import ctypes
import requests
import re

from config import SERVER_HOST, SERVER_PORT, API_KEY

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
    # Taskbar Icon Separation (Forces Windows to drop the Python logo)
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

# Fonts (+10% Scaled, Locked to Consolas)
FONT_MAIN = ("Consolas", 12)
FONT_BOLD = ("Consolas", 12, "bold")
FONT_CODE = ("Consolas", 12)
FONT_UI = ("Consolas", 9, "bold")

SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

# --- SYMMETRICAL ASCII LOGO ---
ASCII_LOGO = """
██████╗ ███████╗██████╗ ██╗██████╗  ██████╗ ████████╗
██╔══██╗██╔════╝██╔══██╗██║██╔══██╗██╔═══██╗╚══██╔══╝
██████╔╝█████╗  ██████╔╝██║██║  ██║██║   ██║   ██║   
██╔═══╝ ██╔══╝  ██╔══██╗██║██║  ██║██║   ██║   ██║   
██║     ███████╗██║  ██║██║██████╔╝╚██████╔╝   ██║   
╚═╝     ╚══════╝╚═╝  ╚═╝╚═╝╚═════╝  ╚═════╝    ╚═╝   
"""
VERSION_TEXT = "SOVEREIGN KERNEL v1.5 [STABLE]\nENGINEERED BY UNCOALESCED"


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
        
        # Load base English lexicon but aggressively enforce UK standards
        if SPELLCHECK_AVAILABLE:
            self.spell = SpellChecker(language='en')
            self.system_words = {"python", "fastapi", "sqlalchemy", "pydantic", "sqlite", "vram", "peridot"}
            
            # The Purge: Eradicate US spellings and enforce UK standards
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
        self._create_widgets()
        self._configure_styles()
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _setup_main_window(self):
        self.root.title("Peridot | Sovereign OS")
        self.root.geometry("1150x800")
        self.root.configure(bg=COLOR_BG)
        
        # Hardened Icon Extraction Pipeline
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.join(base_dir, "assets", "ui", "logo", "peridot.ico")
            self.root.iconbitmap(icon_path)
            
            # Direct User32 handle intercept to strip old cached window mappings immediately
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if hwnd:
                hicon = ctypes.windll.user32.LoadImageW(0, icon_path, 1, 0, 0, 0x00000010 | 0x00000020)
                ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, hicon) # Set big icon
                ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, hicon) # Set small icon
        except Exception:
            pass

        # Dark Title Bar (Windows 11)
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(2)), 4)
        except:
            pass

    def _create_widgets(self):
        # Chat Buffer
        self.out_frame = tk.Frame(self.root, bg=COLOR_BG)
        self.out_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(20, 10))
        self.chat = scrolledtext.ScrolledText(
            self.out_frame, wrap=tk.WORD, bg=COLOR_BG, fg=COLOR_TEXT,
            font=FONT_MAIN, insertbackground=COLOR_ACCENT, bd=0,
            highlightthickness=0, padx=10, pady=10, state=tk.DISABLED
        )
        self.chat.pack(fill=tk.BOTH, expand=True)

        # Responsive Grid Manager Setup (Prevents Execution Button Squash)
        self.in_frame = tk.Frame(self.root, bg=COLOR_BG)
        self.in_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        tk.Frame(self.in_frame, bg=COLOR_ACCENT, height=2).grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 10))
        
        self.in_frame.columnconfigure(0, weight=1) # Input field consumes excess geometry
        self.in_frame.columnconfigure(1, weight=0) # Mic static sizing
        self.in_frame.columnconfigure(2, weight=0) # Execute static sizing

        # Expanding Input Fields
        self.entry = tk.Text(
            self.in_frame, bg=COLOR_INPUT, fg="white", font=FONT_MAIN,
            insertbackground=COLOR_ACCENT, relief=tk.FLAT, bd=5, height=1, width=1, wrap=tk.WORD
        )
        self.entry.grid(row=1, column=0, sticky="ew", ipady=5)
        
        # Key Layout Configurations
        self.entry.bind("<Return>", self._on_enter)
        self.entry.bind("<Shift-Return>", self._on_shift_enter)
        self.entry.bind("<KeyRelease>", self._on_key_release)
        self.entry.bind("<Button-3>", self._show_spellcheck_menu) # Right-click context loop

        # Symmetrical Layout Clamping
        self.btn_mic = tk.Button(
            self.in_frame, text="MIC", command=self.handle_voice, bg=COLOR_DIM, fg="white",
            font=("Consolas", 10, "bold"), relief=tk.FLAT, padx=15, pady=5, cursor="hand2"
        )
        self.btn_mic.grid(row=1, column=1, padx=(10, 5), sticky="ns")

        self.btn_run = tk.Button(
            self.in_frame, text="EXECUTE", command=self.handle_input, bg=COLOR_ACCENT, fg="black",
            font=("Consolas", 10, "bold"), relief=tk.FLAT, padx=15, pady=5, cursor="hand2"
        )
        self.btn_run.grid(row=1, column=2, padx=5, sticky="ns")

        # Glass Box Telemetry Status Bar
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

    def _mk_btn(self, txt, cmd, bg=COLOR_DIM, fg="white"):
        return tk.Button(
            self.in_frame, text=txt, command=cmd, bg=bg, fg=fg,
            font=("Consolas", 10, "bold"), relief=tk.FLAT, padx=15, pady=5, cursor="hand2"
        )

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
        
        # Spellcheck underline tag declaration
        self.entry.tag_config("misspelled", underline=True, underlinefg=COLOR_ERROR)

    # --- SPELLCHECK ARBITRATION (UK ENGLISH) ---
    def _run_spellcheck(self):
        """Asynchronously parses input matrix to locate non-UK English strings."""
        if not SPELLCHECK_AVAILABLE:
            return
            
        self.entry.tag_remove("misspelled", "1.0", tk.END)
        content = self.entry.get("1.0", "end-1c")
        
        # Basic alphanumeric isolate block
        words = re.finditer(r'\b[a-zA-Z]+\b', content)
        for match in words:
            word = match.group()
            if len(word) > 2:
                # Check against the en dictionary (which has been purged of US spellings)
                if word.lower() not in self.spell:
                    start_idx = f"1.0 + {match.start()} chars"
                    end_idx = f"1.0 + {match.end()} chars"
                    self.entry.tag_add("misspelled", start_idx, end_idx)

    def _apply_correction(self, start, end, correct_word):
        self.entry.delete(start, end)
        self.entry.insert(start, correct_word)
        self._run_spellcheck()

    def _show_spellcheck_menu(self, event):
        """Generates screen-space suggestion panel upon right-click handles."""
        if not SPELLCHECK_AVAILABLE:
            return
            
        try:
            index = self.entry.index(f"@{event.x},{event.y}")
            tags = self.entry.tag_names(index)
            
            if "misspelled" in tags:
                menu = tk.Menu(self.root, tearoff=0, bg=COLOR_DIM, fg="white", activebackground=COLOR_ACCENT, activeforeground="black", font=FONT_UI)
                
                # Extract word bounds near cursor coordinates
                start = self.entry.index(f"{index} wordstart")
                end = self.entry.index(f"{index} wordend")
                target_word = self.entry.get(start, end)

                # Get candidates
                candidates = self.spell.candidates(target_word.lower())
                
                if candidates:
                    for idx, candidate in enumerate(candidates):
                        if idx > 4: break # Limit to top 5 suggestions
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
        # Debounce the spellcheck slightly so it doesn't stutter on fast typing
        if hasattr(self, '_spellcheck_timer'):
            self.root.after_cancel(self._spellcheck_timer)
        self._spellcheck_timer = self.root.after(500, self._run_spellcheck)

    def _adjust_input_height(self, event=None):
        num_lines = int(self.entry.index('end-1c').split('.')[0])
        new_height = min(max(1, num_lines), 8)
        self.entry.config(height=new_height)

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
        blocks = text.split("```")
        
        for i, block in enumerate(blocks):
            if i % 2 == 0:
                # Standard Text Payload
                if block:
                    self.chat.insert(tk.END, block, "ai")
            else:
                # Code Block Payload
                lines = block.split('\n', 1)
                lang = lines[0].strip() if len(lines) > 1 else ""
                code_content = lines[1] if len(lines) > 1 else block
                code_content = code_content.strip()
                
                if code_content:
                    self.chat.insert(tk.END, "\n")
                    
                    # Generate Interactive Header Frame
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
                    
                    # Inject Frame and Styled Code into Tkinter Buffer
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
            self.display_system_message("Failed to toggle Research Cluster. Engine offline.")

    def _poll_backend_telemetry(self):
        """Actively pulls real-time FSM states from the Neural Engine"""
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
            # OS Hardware Polling
            self.bar_cpu.update_value(psutil.cpu_percent())
            self.bar_ram.update_value(psutil.virtual_memory().percent)
            
            # NVIDIA VRAM Polling
            c = "nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits"
            o = subprocess.check_output(c, shell=True, creationflags=0x08000000).decode().strip().split(",")
            self.bar_vram.update_value((int(o[0]) / int(o[1])) * 100)
            
            # Backend FSM Polling
            threading.Thread(target=self._poll_backend_telemetry, daemon=True).start()
        except:
            pass
        self.root.after(1500, self._update_stats)

    def run(self):
        self.print_logo()
        self._update_stats()
        threading.Thread(target=self.core.start, daemon=True).start()
        self.root.mainloop()

    def _on_closing(self):
        self.root.destroy()
        os._exit(0)