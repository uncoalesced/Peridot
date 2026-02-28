import hashlib
import json
import os

# --- FIXED IMPORT ---
from core_system.enhancedlogger import get_instance as get_logger

HASH_FILE = "integrity_hashes.json"


class IntegrityChecker:
    def __init__(self):
        self.logger = get_logger()
        self.hashes = self._load_hashes()

    def _load_hashes(self):
        if not os.path.exists(HASH_FILE):
            return {}
        try:
            with open(HASH_FILE, "r") as f:
                return json.load(f)
        except:
            return {}

    def calculate_file_hash(self, filepath):
        """Calculates SHA-256 hash of a file."""
        sha256_hash = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except FileNotFoundError:
            return None

    def verify_file(self, filepath):
        """Returns True if file matches stored hash."""
        stored_hash = self.hashes.get(filepath)
        if not stored_hash:
            return True  # New file, assume safe for now (or strictly return False)

        current_hash = self.calculate_file_hash(filepath)
        if current_hash != stored_hash:
            self.logger.warning(f"Integrity Mismatch: {filepath}", source="INTEGRITY")
            return False
        return True
