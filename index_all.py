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
Runner: Index All
Automated ingestion of authorized payloads into Semantic Memory.
# Engineered by uncoalesced
"""

import sys
import os
from pathlib import Path

# -----------------------------------------------------------------------------
# PATH BOOTSTRAPPING
# -----------------------------------------------------------------------------
root_dir = Path(__file__).parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

try:
    from core_system.enhancedlogger import logger
    from core_system.ingestion.file_processor import (
        read_text_file, read_pdf_file, get_all_ingestible_files
    )
    from core_system.ingestion.vector_store import vector_store
except ImportError as e:
    print(f"[ERROR] Failed to load core ingestion modules: {e}")
    sys.exit(1)

def run_indexing():
    logger.info("\n" + "="*60)
    logger.info("PERIDOT KERNEL | SEMANTIC INGESTION SEQUENCE")
    logger.info("="*60 + "\n")

    # 1. DISCOVERY
    files = get_all_ingestible_files()
    if not files:
        logger.warning("No valid payloads detected in E:\\Peridot\\input", source="INGEST")
        return

    logger.info(f"Discovered {len(files)} potential documents for indexing.", source="INGEST")

    # 2. EXTRACTION & EMBEDDING
    for filename in files:
        logger.info(f"Processing: {filename}", source="INGEST")
        
        content = ""
        ext = Path(filename).suffix.lower()

        if ext in [".txt", ".md"]:
            content = read_text_file(filename)
        elif ext == ".pdf":
            content = read_pdf_file(filename)
        
        if not content:
            logger.error(f"Failed to extract content from {filename}", source="INGEST")
            continue

        # 3. COMMIT TO MEMORY (v1.3.2 Deduplication Logic)
        # This will automatically skip if the file hasn't changed (SHA-256 Check)
        vector_store.add_document(content, filename)

    logger.info("Ingestion sequence complete.", source="INGEST")

if __name__ == "__main__":
    run_indexing()