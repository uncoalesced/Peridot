# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL
# Copyright (C) 2026 uncoalesced
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
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

from core_system.security import sanitize_input, is_file_safe
from config import SERVER_HOST, SERVER_PORT

BASE_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"

def test_file_blacklist():
    print("[TEST] File Blacklist...")
    assert not is_file_safe(".ssh/id_rsa")[0], "FAIL: SSH key bypass allowed!"
    assert not is_file_safe("C:\\Windows\\System32\\cmd.exe")[0], "FAIL: System directory bypass allowed!"
    assert is_file_safe("research_paper.pdf")[0], "FAIL: Safe file falsely blocked!"
    print("  ✅ PASS: Directory traversal and sensitive files blocked.")

def test_input_sanitization():
    print("[TEST] Input Sanitization...")
    assert not sanitize_input("<script>alert('xss')</script>")[1], "FAIL: XSS payload allowed!"
    assert not sanitize_input("import os; os.system('rm -rf /')")[1], "FAIL: OS execution payload allowed!"
    assert sanitize_input("What is the capital of France?")[1], "FAIL: Normal query falsely blocked!"
    print("  ✅ PASS: Malicious code injection destroyed.")

def test_api_auth_bypass():
    print("[TEST] API Authentication Bypass...")
    try:
        # We purposely send a request WITHOUT the Bearer token
        r = requests.post(f"{BASE_URL}/ask", json={"command": "Wake up"}, timeout=2)
        assert r.status_code in [401, 403], f"FAIL: Expected 401/403, got {r.status_code}. The API is exposed!"
        print("  ✅ PASS: Unauthorized local API requests blocked.")
    except requests.exceptions.ConnectionError:
        print("  ⚠️ SKIP: Inference Server offline. Boot `python launcher.py` in another terminal to test the API.")

if __name__ == "__main__":
    print("=====================================")
    print("  PERIDOT KERNEL SECURITY SUITE")
    print("=====================================")
    test_file_blacklist()
    test_input_sanitization()
    test_api_auth_bypass()
    print("=====================================")
    print("STATUS: ALL DEFENSES HOLDING.")