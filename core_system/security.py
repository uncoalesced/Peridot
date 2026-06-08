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
SENSITIVE_DIRS = ["C:\\Windows\\", "/etc/", "/root/", "/boot/"]

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

def is_file_safe(filepath: str) -> tuple[bool, str]:
    """Task 2: File Access Blacklist"""
    abs_path = os.path.abspath(filepath)
    path_lower = abs_path.lower()
    
    for pattern in FILE_BLACKLIST:
        if pattern in path_lower:
            log_event("FILE_DENIED", f"Blacklisted file: {pattern}", "WARNING")
            return False, f"Access to {pattern} is restricted."
            
    for s_dir in SENSITIVE_DIRS:
        if abs_path.startswith(os.path.abspath(s_dir)):
            log_event("FILE_DENIED", f"Sensitive directory: {s_dir}", "WARNING")
            return False, f"Access to system directory {s_dir} is restricted."
            
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