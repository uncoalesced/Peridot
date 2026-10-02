# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL v1.6.0 | PLUGIN SANDBOX CHILD
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
Trusted runner for one untrusted plugin tool call.

Launched by core_system/extensions/sandbox.py as `python -I sandbox_child.py
<json payload>`. It imports nothing from Peridot: -I keeps the cwd off
sys.path, and the plugin must never see kernel modules pre-imported.

Order matters: resource limits (needs ctypes) -> audit-hook policy -> plugin.

# ponytail: audit hooks are defense-in-depth, NOT a kernel sandbox. A hostile
# plugin can bypass them (native extension modules, closure-cell tampering,
# frame walking). Install-time approval is the real gate. Planned upgrade:
# AppContainer (Windows) / Landlock (Linux) for kernel-enforced isolation.
"""

import importlib.util
import json
import math
import os
import sys
import sysconfig

MAX_RESULT_CHARS = 20000

# Always denied once setup is done.
_DENY_EXACT = frozenset({
    "subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.spawn",
    "os.startfile", "os.kill", "os.killpg", "os.fork", "os.forkpty",
    "pty.spawn", "_winapi.CreateProcess",
    "gc.get_objects", "gc.get_referrers", "gc.get_referents",
})
_DENY_PREFIX = ("winreg.", "ctypes.")
_NET_EVENTS = frozenset({
    "socket.__new__", "socket.connect", "socket.bind", "socket.getaddrinfo",
    "socket.sendto", "socket.sendmsg", "socket.gethostbyname",
    "socket.gethostbyname_ex", "socket.gethostbyaddr",
})
# Every path argument must fall inside write_paths.
_WRITE_EVENTS = frozenset({
    "os.remove", "os.rename", "os.rmdir", "os.mkdir", "shutil.rmtree",
    "os.truncate", "os.chmod", "os.chown", "os.utime", "os.symlink", "os.link",
})
# Directory listings: every path argument must be readable.
_LIST_EVENTS = frozenset({"os.listdir", "os.scandir"})
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC


def _limit_windows(mem_mb: int):
    """Put this process in a Job Object. Returns (handle, note); keep handle alive."""
    import ctypes
    from ctypes import wintypes

    class _Basic(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _Io(ctypes.Structure):
        _fields_ = [(n, ctypes.c_uint64) for n in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class _Extended(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _Basic),
            ("IoInfo", _Io),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateJobObjectW.restype = wintypes.HANDLE
    k32.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR)
    k32.SetInformationJobObject.restype = wintypes.BOOL
    k32.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD)
    k32.AssignProcessToJobObject.restype = wintypes.BOOL
    k32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    k32.GetCurrentProcess.restype = wintypes.HANDLE

    job = k32.CreateJobObjectW(None, None)
    if not job:
        return None, f"job: CreateJobObject failed ({ctypes.get_last_error()})"

    info = _Extended()
    info.BasicLimitInformation.LimitFlags = (
        0x00000100    # JOB_OBJECT_LIMIT_PROCESS_MEMORY
        | 0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        | 0x00000008  # JOB_OBJECT_LIMIT_ACTIVE_PROCESS
        | 0x00000400  # JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION
    )
    info.BasicLimitInformation.ActiveProcessLimit = 1
    info.ProcessMemoryLimit = int(mem_mb) * 1024 * 1024
    if not k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):  # 9 = JobObjectExtendedLimitInformation
        return job, f"job: SetInformationJobObject failed ({ctypes.get_last_error()})"
    if not k32.AssignProcessToJobObject(job, k32.GetCurrentProcess()):
        # Pre-Win8 hosts refuse nested jobs; carry on with audit hooks only.
        return job, f"job: AssignProcessToJobObject failed ({ctypes.get_last_error()})"
    return job, "job: assigned"


def _limit_posix(mem_mb: int, cpu_s: float) -> str:
    import resource

    notes = []
    mem = int(mem_mb) * 1024 * 1024
    for name, value in (("RLIMIT_AS", mem), ("RLIMIT_CPU", math.ceil(cpu_s) + 1), ("RLIMIT_NPROC", 0)):
        limit = getattr(resource, name, None)
        if limit is None:
            continue
        try:
            resource.setrlimit(limit, (value, value))
            notes.append(name)
        except (ValueError, OSError) as exc:
            notes.append(f"{name} failed ({exc})")
    return "rlimit: " + ", ".join(notes)


def _install_policy(plugin_dir: str, policy: dict, denials: list) -> None:
    """Install the audit hook. State is captured in this closure as tuples, not module globals."""

    def norm(p) -> str:
        return os.path.normcase(os.path.realpath(os.fsdecode(p)))

    def roots(paths) -> tuple:
        return tuple(r.rstrip(os.sep) + os.sep for r in (norm(p) for p in paths if p))

    paths = sysconfig.get_paths()
    sys_dirs = [sys.prefix, sys.base_prefix, sys.exec_prefix, sys.base_exec_prefix,
                *(paths.get(k) for k in ("stdlib", "platstdlib", "purelib", "platlib")),
                *(p for p in sys.path if p)]
    write_roots = roots(policy.get("write_paths") or [])
    read_roots = write_roots + roots(policy.get("read_paths") or []) + roots([plugin_dir]) + roots(sys_dirs)
    network = bool(policy.get("network"))

    def allowed(path, rs) -> bool:
        p = norm(path)
        return any((p + os.sep).startswith(r) for r in rs)

    def deny(event, detail):
        denials.append(f"{event}: {detail}")
        raise PermissionError(f"sandbox denied {event}: {detail}")

    def hook(event, args):
        if event == "open":
            path, mode, flags = args[0], args[1], args[2]
            if path is None or isinstance(path, int):
                return  # already-open fd
            if isinstance(mode, str):
                write = any(c in mode for c in "wax+")
            else:
                write = bool((flags or 0) & _WRITE_FLAGS)
            if not allowed(path, write_roots if write else read_roots):
                deny(event, f"{'write' if write else 'read'} {path!r}")
        elif event in _NET_EVENTS:
            if not network:
                deny(event, "network disabled")
        elif event in _DENY_EXACT or event.startswith(_DENY_PREFIX):
            deny(event, "not permitted")
        elif event in _WRITE_EVENTS or event in _LIST_EVENTS:
            rs = write_roots if event in _WRITE_EVENTS else read_roots
            for a in args:
                if isinstance(a, (str, bytes, os.PathLike)) and not allowed(a, rs):
                    deny(event, repr(a))

    sys.addaudithook(hook)


def main() -> None:
    out = sys.stdout
    payload = json.loads(sys.argv[1])
    plugin_dir = payload["plugin_dir"]
    policy = payload.get("policy") or {}
    mem_mb = int(policy.get("mem_mb") or 512)
    meta = {}

    # a+b. Resource limits, while ctypes is still allowed.
    if sys.platform == "win32":
        try:
            _job, meta["limits"] = _limit_windows(mem_mb)
        except Exception as exc:  # never let limit setup kill the run silently
            _job, meta["limits"] = None, f"job: error ({exc})"
    else:
        meta["limits"] = _limit_posix(mem_mb, float(payload.get("timeout") or 30))

    # c. Policy hook before any plugin code is touched.
    sys.dont_write_bytecode = True
    denials: list = []
    _install_policy(plugin_dir, policy, denials)

    # d. Load and call. Plugin prints go to stderr so stdout carries only our JSON.
    result = {"ok": False, "result": "", "error": "", "denied": False}
    sys.stdout = sys.stderr
    try:
        sys.path.insert(0, plugin_dir)
        spec = importlib.util.spec_from_file_location("peridot_plugin", os.path.join(plugin_dir, payload["entry"]))
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load entry {payload['entry']!r}")
        module = importlib.util.module_from_spec(spec)
        sys.modules["peridot_plugin"] = module
        spec.loader.exec_module(module)
        fn = getattr(module, payload["tool"])
        result["result"] = str(fn(**(payload.get("args") or {})))[:MAX_RESULT_CHARS]
        result["ok"] = True
    except PermissionError as exc:
        result["error"] = f"PermissionError: {exc}"
        result["denied"] = True
    except BaseException as exc:  # incl. MemoryError / SystemExit from the plugin
        result["error"] = f"{type(exc).__name__}: {exc}"[:2000]

    # A plugin that swallowed a denial still tripped the policy.
    if denials:
        result["denied"] = True
        meta["denials"] = denials[:20]
    result["meta"] = meta

    # e. Exactly one JSON line, then hard-exit so plugin atexit/threads can't append.
    try:
        sys.stderr.flush()
    except Exception:
        pass
    out.write(json.dumps(result) + "\n")
    out.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
