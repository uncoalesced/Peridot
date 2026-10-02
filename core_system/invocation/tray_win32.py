# -----------------------------------------------------------------------------
# PERIDOT INVOCATION TRAY | Win32 Notification Icon via ctypes (v1.6.0)
# Copyright (C) 2026 uncoalesced
#
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------
# Window + message loop live on the main thread (a window belongs to the thread
# that created it); the relay loop runs on a worker and posts WM_CLOSE when it
# stops. Importing this module creates nothing.

import ctypes
import subprocess
import sys
import threading
from ctypes import wintypes
from pathlib import Path

from config import BASE_DIR

LRESULT = ctypes.c_ssize_t
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t
HWND = HANDLE = ctypes.c_void_p
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, HWND, wintypes.UINT, WPARAM, LPARAM)

WM_NULL, WM_DESTROY, WM_CLOSE = 0x0000, 0x0002, 0x0010
WM_LBUTTONUP, WM_RBUTTONUP, WM_CONTEXTMENU = 0x0202, 0x0205, 0x007B
WM_TRAY = 0x8001  # WM_APP + 1
NIM_ADD, NIM_DELETE = 0, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP = 0x1, 0x2, 0x4
MF_STRING, MF_GRAYED, MF_SEPARATOR = 0x0, 0x1, 0x800
TPM_RIGHTBUTTON, TPM_NONOTIFY, TPM_RETURNCMD = 0x2, 0x80, 0x100
IMAGE_ICON, LR_LOADFROMFILE, LR_DEFAULTSIZE = 1, 0x10, 0x40
IDI_APPLICATION = 32512
CREATE_NEW_CONSOLE = 0x10

ID_OPEN, ID_UNLOAD, ID_STATUS, ID_QUIT = 1, 2, 3, 4
TOOLTIP = "Peridot — Sovereign Invocation"
ICON_PATH = Path(BASE_DIR) / "assets" / "logos" / "peridot.ico"


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", HANDLE), ("hIcon", HANDLE), ("hCursor", HANDLE),
                ("hbrBackground", HANDLE), ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR)]


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", HWND), ("uID", wintypes.UINT),
                ("uFlags", wintypes.UINT), ("uCallbackMessage", wintypes.UINT),
                ("hIcon", HANDLE), ("szTip", ctypes.c_wchar * 128),
                ("dwState", wintypes.DWORD), ("dwStateMask", wintypes.DWORD),
                ("szInfo", ctypes.c_wchar * 256), ("uVersion", wintypes.UINT),
                ("szInfoTitle", ctypes.c_wchar * 64), ("dwInfoFlags", wintypes.DWORD),
                ("guidItem", GUID), ("hBalloonIcon", HANDLE)]


class MSG(ctypes.Structure):
    _fields_ = [("hwnd", HWND), ("message", wintypes.UINT), ("wParam", WPARAM),
                ("lParam", LPARAM), ("time", wintypes.DWORD), ("pt", wintypes.POINT),
                ("lPrivate", wintypes.DWORD)]


_api = None


def _win32():
    """Bind user32/shell32/kernel32 with full prototypes (lazily: import stays inert)."""
    global _api
    if _api is not None:
        return _api
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    def bind(dll, name, restype, *argtypes):
        fn = getattr(dll, name)
        fn.restype, fn.argtypes = restype, list(argtypes)
        return fn

    U, L = wintypes.UINT, wintypes.LPCWSTR
    _api = {
        "GetModuleHandleW": bind(kernel32, "GetModuleHandleW", HANDLE, L),
        "RegisterClassW": bind(user32, "RegisterClassW", wintypes.ATOM, ctypes.POINTER(WNDCLASSW)),
        "UnregisterClassW": bind(user32, "UnregisterClassW", wintypes.BOOL, L, HANDLE),
        "CreateWindowExW": bind(user32, "CreateWindowExW", HWND, wintypes.DWORD, L, L, wintypes.DWORD,
                                ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                HWND, HANDLE, HANDLE, ctypes.c_void_p),
        "DestroyWindow": bind(user32, "DestroyWindow", wintypes.BOOL, HWND),
        "DefWindowProcW": bind(user32, "DefWindowProcW", LRESULT, HWND, U, WPARAM, LPARAM),
        "GetMessageW": bind(user32, "GetMessageW", wintypes.BOOL, ctypes.POINTER(MSG), HWND, U, U),
        "TranslateMessage": bind(user32, "TranslateMessage", wintypes.BOOL, ctypes.POINTER(MSG)),
        "DispatchMessageW": bind(user32, "DispatchMessageW", LRESULT, ctypes.POINTER(MSG)),
        "PostMessageW": bind(user32, "PostMessageW", wintypes.BOOL, HWND, U, WPARAM, LPARAM),
        "PostQuitMessage": bind(user32, "PostQuitMessage", None, ctypes.c_int),
        "RegisterWindowMessageW": bind(user32, "RegisterWindowMessageW", U, L),
        "CreatePopupMenu": bind(user32, "CreatePopupMenu", HANDLE),
        "AppendMenuW": bind(user32, "AppendMenuW", wintypes.BOOL, HANDLE, U, ctypes.c_size_t, L),
        "TrackPopupMenu": bind(user32, "TrackPopupMenu", wintypes.BOOL, HANDLE, U, ctypes.c_int,
                               ctypes.c_int, ctypes.c_int, HWND, ctypes.c_void_p),
        "DestroyMenu": bind(user32, "DestroyMenu", wintypes.BOOL, HANDLE),
        "GetCursorPos": bind(user32, "GetCursorPos", wintypes.BOOL, ctypes.POINTER(wintypes.POINT)),
        "SetForegroundWindow": bind(user32, "SetForegroundWindow", wintypes.BOOL, HWND),
        "LoadImageW": bind(user32, "LoadImageW", HANDLE, HANDLE, L, U, ctypes.c_int, ctypes.c_int, U),
        "LoadIconW": bind(user32, "LoadIconW", HANDLE, HANDLE, ctypes.c_void_p),
        "DestroyIcon": bind(user32, "DestroyIcon", wintypes.BOOL, HANDLE),
        "Shell_NotifyIconW": bind(shell32, "Shell_NotifyIconW", wintypes.BOOL, wintypes.DWORD,
                                  ctypes.POINTER(NOTIFYICONDATAW)),
    }
    return _api


def open_peridot():
    """Launch launcher.py in its own console, detached from the relay."""
    exe = Path(sys.executable)
    console = exe.with_name("python.exe")  # pythonw has no console for the TUI
    subprocess.Popen([str(console if console.exists() else exe), str(Path(BASE_DIR) / "launcher.py")],
                     cwd=str(BASE_DIR), creationflags=CREATE_NEW_CONSOLE, close_fds=True)


class Tray:
    CLASS_NAME = "PeridotInvocationRelayTray"

    def __init__(self, relay):
        self.relay = relay
        self.api = _win32()
        self.hwnd = None
        self.hicon = None
        self._owns_icon = False
        self._wndproc = WNDPROC(self._proc)  # keep a reference: ctypes callbacks are GC-able
        self._taskbar_created = self.api["RegisterWindowMessageW"]("TaskbarCreated")

    def create(self):
        a = self.api
        hinst = a["GetModuleHandleW"](None)
        wc = WNDCLASSW(lpfnWndProc=self._wndproc, hInstance=hinst, lpszClassName=self.CLASS_NAME)
        if not a["RegisterClassW"](ctypes.byref(wc)):
            raise ctypes.WinError(ctypes.get_last_error())
        # Hidden top-level window, not HWND_MESSAGE: message-only windows never
        # receive the TaskbarCreated broadcast needed after an Explorer restart.
        self.hwnd = a["CreateWindowExW"](0, self.CLASS_NAME, "Peridot Relay", 0, 0, 0, 0, 0,
                                         None, None, hinst, None)
        if not self.hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
        if ICON_PATH.exists():
            self.hicon = a["LoadImageW"](None, str(ICON_PATH), IMAGE_ICON, 0, 0,
                                         LR_LOADFROMFILE | LR_DEFAULTSIZE)
            self._owns_icon = bool(self.hicon)
        if not self.hicon:
            self.hicon = a["LoadIconW"](None, IDI_APPLICATION)
        self._notify(NIM_ADD)

    def _notify(self, msg):
        nid = NOTIFYICONDATAW(cbSize=ctypes.sizeof(NOTIFYICONDATAW), hWnd=self.hwnd, uID=1,
                              uFlags=NIF_ICON | NIF_MESSAGE | NIF_TIP,
                              uCallbackMessage=WM_TRAY, hIcon=self.hicon, szTip=TOOLTIP)
        return self.api["Shell_NotifyIconW"](msg, ctypes.byref(nid))

    def _menu(self):
        a = self.api
        menu = a["CreatePopupMenu"]()
        try:
            a["AppendMenuW"](menu, MF_STRING, ID_OPEN, "Open Peridot")
            a["AppendMenuW"](menu, MF_STRING, ID_UNLOAD, "Unload model now")
            a["AppendMenuW"](menu, MF_STRING | MF_GRAYED, ID_STATUS, f"Status: {self.relay.status()}")
            a["AppendMenuW"](menu, MF_SEPARATOR, 0, None)
            a["AppendMenuW"](menu, MF_STRING, ID_QUIT, "Quit")
            pt = wintypes.POINT()
            a["GetCursorPos"](ctypes.byref(pt))
            a["SetForegroundWindow"](self.hwnd)  # else the menu never dismisses
            cmd = a["TrackPopupMenu"](menu, TPM_RIGHTBUTTON | TPM_RETURNCMD | TPM_NONOTIFY,
                                      pt.x, pt.y, 0, self.hwnd, None)
            a["PostMessageW"](self.hwnd, WM_NULL, 0, 0)
        finally:
            a["DestroyMenu"](menu)
        if cmd == ID_OPEN:
            # Launcher boots its own server; two models do not fit one GPU.
            self.relay.unload_now("Open Peridot")
            open_peridot()
        elif cmd == ID_UNLOAD:
            self.relay.unload_now("tray")
        elif cmd == ID_QUIT:
            self.relay.request_quit()  # worker exits its loop and posts WM_CLOSE

    def _proc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_TRAY and (lparam & 0xFFFF) in (WM_LBUTTONUP, WM_RBUTTONUP, WM_CONTEXTMENU):
                self._menu()
                return 0
            if msg == self._taskbar_created:
                self._notify(NIM_ADD)
                return 0
            if msg == WM_DESTROY:
                self._notify(NIM_DELETE)
                if self._owns_icon:
                    self.api["DestroyIcon"](self.hicon)
                self.api["PostQuitMessage"](0)
                return 0
        except Exception:
            pass  # an exception must not escape into the Win32 callback
        return self.api["DefWindowProcW"](hwnd, msg, wparam, lparam)

    def close(self):
        """Thread-safe: ask the tray thread to tear down."""
        if self.hwnd:
            self.api["PostMessageW"](self.hwnd, WM_CLOSE, 0, 0)

    def loop(self):
        a, msg = self.api, MSG()
        while a["GetMessageW"](ctypes.byref(msg), None, 0, 0) > 0:
            a["TranslateMessage"](ctypes.byref(msg))
            a["DispatchMessageW"](ctypes.byref(msg))
        a["UnregisterClassW"](self.CLASS_NAME, a["GetModuleHandleW"](None))


def run(relay):
    """Tray on this (main) thread, relay loop on a worker. Returns when either quits."""
    tray = Tray(relay)
    tray.create()

    def worker():
        try:
            relay.run()
        finally:
            tray.close()

    t = threading.Thread(target=worker, name="peridot-relay", daemon=True)
    t.start()
    try:
        tray.loop()
    finally:
        relay.request_quit()
        t.join(timeout=5)
