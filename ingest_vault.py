#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | VAULT INGESTION AUTOMATION
# Copyright (C) 2026 uncoalesced
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import os
import sys
import logging
import requests
from pathlib import Path
from config import SERVER_HOST, SERVER_PORT, API_KEY

# Initialize explicit logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s | [INGEST] %(message)s")
logger = logging.getLogger("Vault-Ingester")

SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

def run_ingestion_sweep():
    logger.info("Initiating system-wide secure text matrix scan...")
    input_dir = Path("input")
        
    if not input_dir.exists():
        logger.error("Physical storage path root 'input' is missing.")
        sys.exit(1)
        
    files = [f for f in os.listdir(input_dir) if f.endswith(('.pdf', '.txt', '.json'))]
    if not files:
        logger.warning("No valid text corpora (.pdf, .txt, .json) detected in ingestion boundary.")
        return

    logger.info(f"Located {len(files)} target nodes. Broadcasting ingestion command to Neural Engine...")
    
    try:
        # Pings the internal core system router to begin multi-threaded semantic chunking
        response = requests.post(f"{SERVER_URL}/ingest", headers=HEADERS, timeout=300)
        if response.status_code == 200:
            logger.info("SUCCESS: Elements securely tokenized, vectorized, and written to FAISS storage.")
            data = response.json()
            logger.info(f"Sectors Updated: {data.get('status', 'OK')}")
        else:
            logger.error(f"FAIL: Core system rejected payload tracking with status code: {response.status_code}")
    except requests.exceptions.ConnectionError:
        logger.error("CRITICAL: Neural Engine offline. Boot server.py before attempting ingestion.")
    except Exception as e:
        logger.error(f"Unexpected pipeline disruption: {e}")

if __name__ == "__main__":
    run_ingestion_sweep()