# in utils/path_checker.py
import os


def validate_path(path_to_check):
    """Placeholder to validate a path exists."""
    if not os.path.exists(path_to_check):
        print(f"Warning: Path '{path_to_check}' does not exist.")
        return False
    return True
