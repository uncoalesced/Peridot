# scripts/file_processor.py

import os
import PyPDF2

# --- FIXED IMPORT ---
from core_system.enhancedlogger import logger


def read_text_file(filepath):
    """Reads a standard .txt file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        logger.info(f"Read text file: {filepath}", source="FILE_IO")
        return content
    except Exception as e:
        logger.error(f"Error reading text file {filepath}: {e}", source="FILE_IO")
        return f"Error reading file: {e}"


def read_pdf_file(filepath):
    """Extracts text from a .pdf file."""
    try:
        text = ""
        with open(filepath, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        logger.info(f"Read PDF file: {filepath}", source="FILE_IO")
        return text
    except Exception as e:
        logger.error(f"Error reading PDF {filepath}: {e}", source="FILE_IO")
        return f"Error reading PDF: {e}"


def read_media_file(filepath):
    """Placeholder for media file reading."""
    logger.info(f"Accessed media file: {filepath}", source="FILE_IO")
    return f"[Media File Detected]: {os.path.basename(filepath)}\n(Media playback not yet supported in terminal)"
