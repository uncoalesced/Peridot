import os

# --- FIXED IMPORT ---
from core_system.enhancedlogger import get_instance as get_logger


class SafeAccessManager:
    def __init__(self, allowed_dirs=None):
        self.logger = get_logger()
        # Default to the current directory and subdirectories
        base_dir = os.path.abspath(os.getcwd())
        self.allowed_dirs = allowed_dirs if allowed_dirs else [base_dir]

    def is_path_safe(self, path):
        """
        Checks if a path is within the allowed directories to prevent
        directory traversal attacks (e.g. ../../../windows/system32).
        """
        try:
            absolute_path = os.path.abspath(path)

            for safe_dir in self.allowed_dirs:
                if absolute_path.startswith(safe_dir):
                    return True

            self.logger.warning(
                f"Access denied to unsafe path: {path}", source="SECURITY"
            )
            return False
        except Exception as e:
            self.logger.error(f"Error checking path safety: {e}", source="SECURITY")
            return False
