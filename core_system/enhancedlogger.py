import logging
import json
import os
import threading
from datetime import datetime

# Define Log Paths
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "system.log")
JSON_LOG_FILE = os.path.join(LOG_DIR, "system.json")

# Ensure logs directory exists
os.makedirs(LOG_DIR, exist_ok=True)


class EnhancedLogger:
    _instance = None
    _lock = threading.Lock()

    @staticmethod
    def get_instance():
        if EnhancedLogger._instance is None:
            with EnhancedLogger._lock:
                if EnhancedLogger._instance is None:
                    EnhancedLogger._instance = EnhancedLogger()
        return EnhancedLogger._instance

    def __init__(self):
        if EnhancedLogger._instance is not None:
            # Prevent re-initialization if someone tries to instantiate directly
            return

        # Setup Standard Logger
        self.logger = logging.getLogger("Peridot-Core")
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False  # Prevent double logging if root logger is used

        # Clear existing handlers to avoid duplicates on reload
        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        # 1. File Handler (Human Readable)
        fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
        fh.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | [%(source)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        self.logger.addHandler(fh)

        # 2. Console Handler (Standard Output)
        ch = logging.StreamHandler()
        ch.setFormatter(
            logging.Formatter(
                "%(asctime)s | [%(source)s] %(message)s", datefmt="%H:%M:%S"
            )
        )
        self.logger.addHandler(ch)

    def _log(self, level, message, source="SYSTEM"):
        """Internal method to handle logging to both text and JSON."""
        extra = {"source": source}

        # Dispatch to standard logger
        if level == "INFO":
            self.logger.info(message, extra=extra)
        elif level == "WARNING":
            self.logger.warning(message, extra=extra)
        elif level == "ERROR":
            self.logger.error(message, extra=extra)
        elif level == "DEBUG":
            self.logger.debug(message, extra=extra)
        elif level == "CRITICAL":
            self.logger.critical(message, extra=extra)

        # Dispatch to JSON Log (Thread-Safe)
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "source": source,
            "message": str(message),
        }

        try:
            with EnhancedLogger._lock:
                with open(JSON_LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(json.dumps(log_entry) + "\n")
        except Exception:
            pass  # Fail silently on JSON write errors to keep system running

    # --- Public API ---
    def info(self, msg, source="SYSTEM"):
        self._log("INFO", msg, source)

    def warning(self, msg, source="SYSTEM"):
        self._log("WARNING", msg, source)

    def error(self, msg, source="SYSTEM"):
        self._log("ERROR", msg, source)

    def debug(self, msg, source="SYSTEM"):
        self._log("DEBUG", msg, source)

    def critical(self, msg, source="SYSTEM"):
        self._log("CRITICAL", msg, source)


# Global Singleton Accessor
logger = EnhancedLogger.get_instance()


def get_instance():
    return logger


def summarize_logs(lines=10):
    """Returns the last N lines from the text log."""
    if not os.path.exists(LOG_FILE):
        return "No logs found."
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            # Efficiently read last N lines
            all_lines = f.readlines()
            return "".join(all_lines[-lines:])
    except Exception as e:
        return f"Error reading logs: {e}"


def summarize_logs_json(lines=5):
    """Returns the last N lines from the JSON log."""
    if not os.path.exists(JSON_LOG_FILE):
        return "No JSON logs found."
    try:
        with open(JSON_LOG_FILE, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            return "".join(all_lines[-lines:])
    except Exception as e:
        return f"Error reading logs: {e}"
