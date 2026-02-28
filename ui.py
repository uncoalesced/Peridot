# ui.py
# PERIDOT SOVEREIGN KERNEL | INTERFACE
# Engineered by uncoalesced.

import tkinter as tk
from tkinter import scrolledtext, font
import threading
import psutil
import time
import subprocess
import os
import ctypes

# --- HIGH DPI FIX ---
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# --- THEME CONFIGURATION ---
COLOR_BG = "#050505"
COLOR_TEXT = "#E0E0E0"
COLOR_ACCENT = "#00FF41"
COLOR_DIM = "#1A1A1A"
COLOR_USER = "#A48EFF"
COLOR_AI = "#E0E0E0"
COLOR_SYSTEM = "#00FF41"
COLOR_ERROR = "#FF2A6D"
COLOR_INPUT = "#0F0F0F"

# --- SYMMETRICAL ASCII LOGO ---
ASCII_LOGO = """
██████╗ ███████╗██████╗ ██╗██████╗  ██████╗ ████████╗
██╔══██╗██╔════╝██╔══██╗██║██╔══██╗██╔═══██╗╚══██╔══╝
██████╔╝█████╗  ██████╔╝██║██║  ██║██║   ██║   ██║   
██╔═══╝ ██╔══╝  ██╔══██╗██║██║  ██║██║   ██║   ██║   
██║     ███████╗██║  ██║██║██████╔╝╚██████╔╝   ██║   
╚═╝     ╚══════╝╚═╝  ╚═╝╚═╝╚═════╝  ╚═════╝    ╚═╝   
"""
VERSION_TEXT = "SOVEREIGN KERNEL v1.2 [BETA]\nENGINEERED BY UNCOALESCED"


class TechProgressBar(tk.Canvas):
    def __init__(self, parent, width=100, height=18, bg=COLOR_DIM):
        super().__init__(
            parent, width=width, height=height, bg=bg, highlightthickness=0
        )
        self.w, self.h = width, height
        self.rect = self.create_rectangle(0, 0, 0, height, fill=COLOR_ACCENT, width=0)
        self.text_shadow = self.create_text(
            width / 2 + 1,
            height / 2 + 1,
            text="0%",
            fill="#000000",
            font=("Consolas", 8, "bold"),
        )
        self.text_main = self.create_text(
            width / 2,
            height / 2,
            text="0%",
            fill="#FFFFFF",
            font=("Consolas", 8, "bold"),
        )

    def update_value(self, percent):
        percent = max(0, min(100, percent))
        col = (
            "#00FF41"
            if percent <= 60
            else (
                "#FFD700"
                if percent <= 85
                else "#FF8C00" if percent <= 95 else "#FF2A6D"
            )
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
        self._setup_main_window()
        self._create_widgets()
        self._configure_styles()
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _setup_main_window(self):
        self.root.title("Peridot | Sovereign OS")
        self.root.geometry("1150x800")
        self.root.configure(bg=COLOR_BG)
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 20, ctypes.byref(ctypes.c_int(2)), 4
            )
        except:
            pass

    def _create_widgets(self):
        self.out_frame = tk.Frame(self.root, bg=COLOR_BG)
        self.out_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(20, 10))
        self.chat = scrolledtext.ScrolledText(
            self.out_frame,
            wrap=tk.WORD,
            bg=COLOR_BG,
            fg=COLOR_TEXT,
            font=("Consolas", 11),
            insertbackground=COLOR_ACCENT,
            bd=0,
            highlightthickness=0,
            padx=10,
            pady=10,
            state=tk.DISABLED,
        )
        self.chat.pack(fill=tk.BOTH, expand=True)

        self.in_frame = tk.Frame(self.root, bg=COLOR_BG)
        self.in_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        tk.Frame(self.in_frame, bg=COLOR_ACCENT, height=2).pack(fill=tk.X, pady=(0, 10))
        self.entry = tk.Entry(
            self.in_frame,
            bg=COLOR_INPUT,
            fg="white",
            font=("Consolas", 12),
            insertbackground=COLOR_ACCENT,
            relief=tk.FLAT,
            bd=5,
        )
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)
        self.entry.bind("<Return>", lambda e: self.handle_input())

        self.btn_mic = self._mk_btn("MIC", self.handle_voice)
        self.btn_mic.pack(side=tk.LEFT, padx=(10, 5))
        self.btn_run = self._mk_btn("EXECUTE", self.handle_input, COLOR_ACCENT, "black")
        self.btn_run.pack(side=tk.LEFT, padx=5)

        self.stat_bar = tk.Frame(self.root, bg="#0A0A0A", height=40)
        self.stat_bar.pack(fill=tk.X, side=tk.BOTTOM)
        self.lbl_status = tk.Label(
            self.stat_bar,
            text="SYSTEM: ONLINE",
            bg="#0A0A0A",
            fg="#666",
            font=("Consolas", 9, "bold"),
        )
        self.lbl_status.pack(side=tk.LEFT, padx=15)
        for m in [("RAM", "bar_ram"), ("CPU", "bar_cpu"), ("VRAM", "bar_vram")]:
            self._add_monitor(m[0], m[1])

    def _mk_btn(self, txt, cmd, bg=COLOR_DIM, fg="white"):
        return tk.Button(
            self.in_frame,
            text=txt,
            command=cmd,
            bg=bg,
            fg=fg,
            font=("Consolas", 10, "bold"),
            relief=tk.FLAT,
            padx=15,
            pady=5,
            cursor="hand2",
        )

    def _add_monitor(self, lbl, var):
        f = tk.Frame(self.stat_bar, bg="#0A0A0A")
        f.pack(side=tk.RIGHT, padx=15, pady=5)
        tk.Label(f, text=lbl, bg="#0A0A0A", fg=COLOR_ACCENT, font=("Consolas", 8)).pack(
            side=tk.LEFT, padx=(0, 5)
        )
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
            self.chat.tag_config(
                tag,
                foreground=col,
                font=("Consolas", 11, "bold") if tag != "ai" else ("Consolas", 11),
            )
        self.chat.tag_config("logo", justify="center")

    def handle_input(self):
        if self.is_processing:
            return
        t = self.entry.get().strip()
        if not t:
            return
        self.entry.delete(0, tk.END)
        self.write(f"\n> {t}\n", "user")
        self._process_async(t)

    def handle_voice(self):
        if self.is_processing:
            return
        self.display_system_message("Listening for command...")
        threading.Thread(target=self._voice_thread, daemon=True).start()

    def _voice_thread(self):
        res = (
            self.core.ears.listen(5)
            if self.core.ears
            else "[ERROR] Audio module missing."
        )
        self.root.after(
            0,
            lambda: (
                self.entry.insert(0, res)
                if "[ERROR]" not in res
                else self.display_system_message(res)
            ),
        )

    def _process_async(self, data):
        self.is_processing = True

        def task():
            try:
                resp = self.core.respond_to_input(data)
            except Exception as e:
                resp = f"[SYSTEM FAILURE] {e}"
            self.root.after(0, self._finish, resp)

        threading.Thread(target=task, daemon=True).start()

    def _finish(self, r):
        self.is_processing = False
        self.write(f"{r}\n", "ai")

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

    def _update_stats(self):
        if not self.root.winfo_exists():
            return
        try:
            self.bar_cpu.update_value(psutil.cpu_percent())
            self.bar_ram.update_value(psutil.virtual_memory().percent)
            c = "nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits"
            o = (
                subprocess.check_output(c, shell=True, creationflags=0x08000000)
                .decode()
                .strip()
                .split(",")
            )
            self.bar_vram.update_value((int(o[0]) / int(o[1])) * 100)
        except:
            pass
        self.root.after(1000, self._update_stats)

    def run(self):
        self.print_logo()
        self._update_stats()
        threading.Thread(target=self.core.start, daemon=True).start()
        self.root.mainloop()

    def _on_closing(self):
        self.root.destroy()
        os._exit(0)
