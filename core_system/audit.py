# Creating the audit.py module

audit_code = """
import datetime
from pathlib import Path

AUDIT_LOG_PATH = Path("D:/iCould/logs/audit.log")

def log_audit_event(event: str, level: str = "INFO"):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as log_file:
        log_file.write(f"[{timestamp}] [{level}] {event}\\n")

def log_unauthorized_access_attempt(path: str):
    log_audit_event(f"Unauthorized access attempt detected for path: {path}", level="WARNING")
"""

# Save this as audit.py
audit_path = Path("/mnt/data/audit.py")
audit_path.write_text(audit_code)

audit_path.name
