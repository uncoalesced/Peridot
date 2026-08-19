# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL
# Copyright (C) 2026 uncoalesced
#
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import re
import os
import json
import logging
from pathlib import Path

# --- CONFIGURATION ---
DANGEROUS_PATTERNS = [r"<script", r"eval\(", r"__import__", r"os\.system", r"subprocess\."]
FILE_BLACKLIST = [".env", ".ssh/", "id_rsa", "passwords.txt", "private.key", "auth.token"]
SENSITIVE_DIRS = ["C:\\Windows\\", "/etc/", "/root/", "/boot/", "/sys/", "/proc/"]

# Model download boundary (v1.5.4). Downloads run in an isolated child process
# (see core_system/model_fetch.py); the main process never leaves offline mode.
APPROVED_MODEL_HOSTS = ["huggingface.co"]
_REPO_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")
_FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

DEFAULT_CONSTITUTION = {
    "allow_file_read": False,
    "allow_file_write": False,
    "allow_code_execute": False,
}

# --- LOGGING SETUP ---
LOG_PATH = Path("logs")
LOG_PATH.mkdir(exist_ok=True)

security_logger = logging.getLogger("Peridot-Security")
security_logger.setLevel(logging.INFO)
if not security_logger.handlers:
    handler = logging.FileHandler(LOG_PATH / "security.log")
    formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s')
    handler.setFormatter(formatter)
    security_logger.addHandler(handler)
    security_logger.propagate = False

def log_event(event_type: str, details: str, severity: str = "INFO"):
    message = f"[{event_type}] {details}"
    if severity == "CRITICAL": security_logger.critical(message)
    elif severity == "WARNING": security_logger.warning(message)
    else: security_logger.info(message)

# --- CORE SECURITY FUNCTIONS ---

def sanitize_input(user_input: str) -> tuple[str, bool]:
    """Task 1: Input Sanitization"""
    if len(user_input) > 10000:
        log_event("INPUT_REJECTED", "Payload too large", "WARNING")
        return "", False
    
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, user_input, re.IGNORECASE):
            log_event("INPUT_REJECTED", f"Dangerous pattern detected: {pattern}", "WARNING")
            return "", False
            
    # Clean up null bytes
    return user_input.replace("\x00", ""), True

def _normalize_path(raw) -> str:
    """
    Collapse a path to a lowercase, forward-slash form for blacklist matching.

    Deliberately does NOT call os.path.abspath: abspath is platform-relative, so
    on Linux it turns "C:\\Windows\\..." into "<cwd>/C:\\Windows\\..." and on
    Windows it turns "/etc/shadow" into "<drive>:\\etc\\shadow". Matching the
    normalized literal keeps both platforms' blacklists enforceable everywhere.
    """
    return str(raw).replace("\\", "/").lower().rstrip("/")

def is_file_safe(filepath: str) -> tuple[bool, str]:
    """Task 2: File Access Blacklist"""
    # Check the literal path AND its resolved form. The literal catches
    # foreign-platform absolute paths; the resolved form catches traversal
    # (e.g. "../../etc/shadow") on the platform we are actually running on.
    candidates = {_normalize_path(filepath), _normalize_path(os.path.abspath(filepath))}

    for pattern in FILE_BLACKLIST:
        needle = _normalize_path(pattern)
        if any(needle in c for c in candidates):
            log_event("FILE_DENIED", f"Blacklisted file: {pattern}", "WARNING")
            return False, f"Access to {pattern} is restricted."

    for s_dir in SENSITIVE_DIRS:
        prefix = _normalize_path(s_dir)
        if any(c == prefix or c.startswith(prefix + "/") for c in candidates):
            log_event("FILE_DENIED", f"Sensitive directory: {s_dir}", "WARNING")
            return False, f"Access to system directory {s_dir} is restricted."

    return True, "OK"

def is_model_download_safe(repo_id: str, filename: str, dest_dir) -> tuple[bool, str]:
    """
    Task 6 (v1.5.4): Model Download Boundary.

    Every outbound model fetch routes through here before a child process is
    spawned. Validates the repo/file identifiers against a strict charset (no
    traversal, no shell metacharacters, no URLs) and confirms the destination
    stays inside the operator's local models directory.
    """
    if not isinstance(repo_id, str) or not _REPO_ID_RE.match(repo_id):
        log_event("DOWNLOAD_DENIED", f"Malformed repo id: {repo_id!r}", "WARNING")
        return False, "Repository identifier rejected. Expected '<owner>/<repo>'."

    if not isinstance(filename, str) or not _FILENAME_RE.match(filename):
        log_event("DOWNLOAD_DENIED", f"Malformed filename: {filename!r}", "WARNING")
        return False, "Filename rejected. Path separators and traversal are not permitted."

    dest = Path(dest_dir).resolve()
    target = (dest / filename).resolve()
    if dest not in target.parents:
        log_event("DOWNLOAD_DENIED", f"Destination escapes model directory: {target}", "CRITICAL")
        return False, "Download destination must remain inside the local models directory."

    log_event("DOWNLOAD_APPROVED", f"{repo_id}/{filename} -> {dest}", "INFO")
    return True, "OK"

def load_constitution(path: str = None) -> dict:
    """Task 5: Constitution Validation"""
    if path is None:
        project_root = Path(__file__).resolve().parent.parent
        resolved_path = project_root / "config" / "constitution.json"
    else:
        resolved_path = Path(path)

    try:
        with open(resolved_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        # Ensure all default keys exist
        for key, value in DEFAULT_CONSTITUTION.items():
            if key not in config:
                config[key] = value
        return config
    except (FileNotFoundError, json.JSONDecodeError):
        # Fallback completely silently
        return DEFAULT_CONSTITUTION.copy()