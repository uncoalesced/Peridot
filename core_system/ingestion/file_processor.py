"""
Module: File Processor (RAG Ingestion)
Handles high-fidelity text extraction strictly from the authorized input directory.
# Engineered by uncoalesced
"""

import os
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("[ERROR] PyMuPDF is missing. Run: pip install PyMuPDF")
    sys.exit(1)

try:
    from core_system.enhancedlogger import logger
except ImportError:
    import logging
    logger = logging.getLogger("file_processor")

# -----------------------------------------------------------------------------
# SECURITY MANDATE: All ingestion must occur inside this isolated zone.
# -----------------------------------------------------------------------------
INPUT_DIR = Path(r"E:\Peridot\input")
INPUT_DIR.mkdir(parents=True, exist_ok=True)


def _secure_resolve(filename: str) -> Path:
    """
    Secures file access to prevent Path Traversal attacks.
    Only allows reads from E:\Peridot\input.
    """
    # Prevent absolute paths from circumventing the input directory
    if Path(filename).is_absolute():
        filename = Path(filename).name

    target_path = (INPUT_DIR / filename).resolve()
    
    # Verify the resolved path is still inside the INPUT_DIR boundary
    if not str(target_path).startswith(str(INPUT_DIR.resolve())):
        logger.error(f"SECURITY BLOCK: Attempted path traversal -> {filename}", source="FILE_IO")
        raise PermissionError(f"Access denied. All ingestion must occur within {INPUT_DIR}")
        
    if not target_path.exists():
        raise FileNotFoundError(f"File not found in input directory: {target_path}")
        
    return target_path


def read_text_file(filename: str) -> str:
    """Reads a standard .txt or .md file from the input directory."""
    try:
        safe_path = _secure_resolve(filename)
        with open(safe_path, "r", encoding="utf-8") as f:
            content = f.read()
        logger.info(f"Ingested text file: {safe_path.name}", source="FILE_IO")
        return content
    except Exception as e:
        logger.error(f"Error reading text file {filename}: {e}", source="FILE_IO")
        return ""


def read_pdf_file(filename: str) -> str:
    """Extracts clean text from a .pdf file in the input directory using PyMuPDF."""
    try:
        safe_path = _secure_resolve(filename)
        text = ""
        doc = fitz.open(safe_path)
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text += page.get_text("text") + "\n\n"
            
        doc.close()
        logger.info(f"Ingested PDF ({len(doc)} pages): {safe_path.name}", source="FILE_IO")
        return text.strip()
    except Exception as e:
        logger.error(f"Error reading PDF {filename}: {e}", source="FILE_IO")
        return ""


def get_all_ingestible_files() -> list:
    """Returns a list of all valid files currently in the input directory."""
    valid_extensions = {".txt", ".md", ".pdf"}
    return [f.name for f in INPUT_DIR.iterdir() if f.is_file() and f.suffix.lower() in valid_extensions]