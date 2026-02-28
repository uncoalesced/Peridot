import json
import os
from urllib.parse import urlparse

# --- FIXED IMPORT ---
from core_system.enhancedlogger import get_instance as get_logger

PERMISSIONS_FILE = "permissions.json"


class PermissionManager:
    def __init__(self):
        self.logger = get_logger()
        self.permissions = self._load_permissions()

    def _load_permissions(self):
        if not os.path.exists(PERMISSIONS_FILE):
            return {"allowed_domains": [], "blocked_domains": []}
        try:
            with open(PERMISSIONS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load permissions: {e}", source="PERMISSIONS")
            return {"allowed_domains": [], "blocked_domains": []}

    def _save_permissions(self):
        try:
            with open(PERMISSIONS_FILE, "w") as f:
                json.dump(self.permissions, f, indent=4)
        except Exception as e:
            self.logger.error(f"Failed to save permissions: {e}", source="PERMISSIONS")

    def get_domain(self, url):
        try:
            parsed = urlparse(url)
            return parsed.netloc
        except:
            return None

    def is_approved(self, url):
        domain = self.get_domain(url)
        if not domain:
            return False

        # Check explicit allow list
        if domain in self.permissions.get("allowed_domains", []):
            return True

        return False

    def approve_domain(self, url):
        domain = self.get_domain(url)
        if domain and domain not in self.permissions["allowed_domains"]:
            self.permissions["allowed_domains"].append(domain)
            self._save_permissions()
            self.logger.info(f"Domain approved: {domain}", source="PERMISSIONS")
