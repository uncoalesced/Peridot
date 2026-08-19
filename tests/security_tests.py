# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL
# Copyright (C) 2026 uncoalesced
# 
# Licensed under the MIT License.
#
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
PERIDOT | SECURITY PENETRATION TESTS
Run this script to barrage the local kernel with malicious payloads 
and verify the active defense perimeter is holding.
"""

import requests
import sys
import os
from pathlib import Path

# Force Python to see the root directory so we can import internal modules
sys.path.insert(0, str(Path(__file__).parent.parent))

# config MUST be imported first: it force-sets the offline sovereignty lock.
from config import SERVER_HOST, SERVER_PORT
from core_system.security import sanitize_input, is_file_safe, is_model_download_safe
from core_system.model_fetch import assert_main_process_offline

BASE_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"

def test_file_blacklist():
    print("[TEST] File Blacklist...")
    assert not is_file_safe(".ssh/id_rsa")[0], "FAIL: SSH key bypass allowed!"

    # Both platform families are asserted unconditionally. The suite runs on a
    # Linux CI runner, where a Windows-only assertion proves nothing -- and vice
    # versa on an operator's Windows box. is_file_safe() matches the normalised
    # literal path, so both blacklists are enforceable on either host.
    assert not is_file_safe("C:\\Windows\\System32\\cmd.exe")[0], "FAIL: Windows system directory bypass allowed!"
    assert not is_file_safe("/etc/shadow")[0], "FAIL: Linux shadow file bypass allowed!"
    assert not is_file_safe("/root/.bashrc")[0], "FAIL: Linux root home bypass allowed!"
    assert not is_file_safe("/boot/vmlinuz")[0], "FAIL: Linux boot partition bypass allowed!"

    # Relative traversal must resolve and get caught on the host we run on.
    if os.name == "posix":
        # Walk up far enough to provably clear the filesystem root ('..' at '/'
        # is a no-op), so this holds regardless of how deeply the CI workspace
        # is nested. A fixed shallow count resolved to /home/etc/shadow on the
        # GitHub runner and asserted nothing -- the guard below catches that.
        traversal = "../" * 20 + "etc/shadow"
        resolved = os.path.abspath(traversal)
        assert resolved == "/etc/shadow", \
            f"Test bug: traversal resolved to {resolved}, not /etc/shadow"
        assert not is_file_safe(traversal)[0], "FAIL: Linux traversal to /etc allowed!"

    assert is_file_safe("research_paper.pdf")[0], "FAIL: Safe file falsely blocked!"
    assert is_file_safe("input/processed/notes.txt")[0], "FAIL: Safe nested file falsely blocked!"
    print("  [PASS] Directory traversal and sensitive files blocked (Windows + Linux).")


def test_model_download_boundary():
    print("[TEST] Model Download Boundary...")
    models_dir = Path(__file__).parent.parent / "models"
    assert is_model_download_safe("Qwen/Qwen3-27B-GGUF", "model.gguf", models_dir)[0], \
        "FAIL: Legitimate model fetch falsely blocked!"
    assert not is_model_download_safe("Qwen/Qwen3", "../../../etc/cron.d/pwn", models_dir)[0], \
        "FAIL: Traversal in download filename allowed!"
    assert not is_model_download_safe("evil; rm -rf /", "model.gguf", models_dir)[0], \
        "FAIL: Shell metacharacters in repo id allowed!"
    assert not is_model_download_safe("https://evil.test/x", "model.gguf", models_dir)[0], \
        "FAIL: Raw URL accepted as repo id!"
    print("  [PASS] Download identifiers validated, destination confined to models/.")


def test_sovereignty_lock():
    print("[TEST] Sovereignty Lock (offline enforcement)...")
    assert os.environ.get("HF_HUB_OFFLINE") == "1", "FAIL: Main process is not in HF offline mode!"
    assert os.environ.get("TRANSFORMERS_OFFLINE") == "1", "FAIL: Main process is not in transformers offline mode!"
    assert_main_process_offline()
    print("  [PASS] Main process air-gapped; downloads confined to isolated child process.")

def test_input_sanitization():
    print("[TEST] Input Sanitization...")
    assert not sanitize_input("<script>alert('xss')</script>")[1], "FAIL: XSS payload allowed!"
    assert not sanitize_input("import os; os.system('rm -rf /')")[1], "FAIL: OS execution payload allowed!"
    assert sanitize_input("What is the capital of France?")[1], "FAIL: Normal query falsely blocked!"
    print("  [PASS] Malicious code injection destroyed.")

def test_api_auth_bypass():
    print("[TEST] API Authentication Bypass...")
    try:
        # We purposely send a request WITHOUT the Bearer token
        r = requests.post(f"{BASE_URL}/ask", json={"command": "Wake up"}, timeout=2)
        assert r.status_code in [401, 403], f"FAIL: Expected 401/403, got {r.status_code}. The API is exposed!"
        print("  [PASS] Unauthorized local API requests blocked.")
    except requests.exceptions.ConnectionError:
        print("  [SKIP] Inference Server offline. Boot `python launcher.py` in another terminal to test the API.")

if __name__ == "__main__":
    print("=====================================")
    print("  PERIDOT KERNEL SECURITY SUITE")
    print("=====================================")
    test_file_blacklist()
    test_input_sanitization()
    test_model_download_boundary()
    test_sovereignty_lock()
    test_api_auth_bypass()
    print("=====================================")
    print("STATUS: ALL DEFENSES HOLDING.")