import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_PATH = os.path.abspath(BASE_DIR)

INPUT_PATH = os.path.join(ROOT_PATH, "input")
PROCESSED_PATH = os.path.join(INPUT_PATH, "processed")

LOG_PATH = os.path.join(ROOT_PATH, "logs")
BACKUP_PATH = os.path.join(ROOT_PATH, "backups")
