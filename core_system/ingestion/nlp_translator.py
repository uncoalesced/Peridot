"""
Module: NLP Translator
Routes ingested text payloads directly to the Peridot Neural Engine.
# Engineered by uncoalesced
"""

import os
import psutil
import requests

try:
    from core_system.enhancedlogger import logger
except ImportError:
    import logging
    logger = logging.getLogger("nlp_translator")


def _get_ephemeral_token() -> str:
    """Scrapes RAM for the active Peridot API key to maintain zero-config security."""
    for proc in psutil.process_iter(['name', 'cmdline', 'environ']):
        try:
            cmd = proc.info.get('cmdline') or []
            if any('server.py' in str(c) or 'launcher.py' in str(c) for c in cmd):
                env = proc.environ()
                if env and 'PERIDOT_AUTH_TOKEN' in env:
                    return env['PERIDOT_AUTH_TOKEN']
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
            
    # Fallback to local process environment
    return os.environ.get("PERIDOT_AUTH_TOKEN", "")


def summarize_text(text: str) -> str:
    """Routes ingested text to the local LLM for dynamic, context-aware summarization."""
    if not text or len(text.strip()) == 0:
        return "No text provided to summarize."

    logger.info("Routing payload to Neural Engine...", source="NLP")

    token = _get_ephemeral_token()
    if not token:
        logger.error("Could not locate PERIDOT_AUTH_TOKEN. Is server.py running?", source="NLP")
        return "[Error]: Sovereign kernel is not active or token is missing."

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    prompt = f"Please provide a concise, highly accurate summary of the following text:\n\n{text}"
    payload = {"command": prompt}

    try:
        response = requests.post(
            "http://127.0.0.1:5000/ask", 
            json=payload, 
            headers=headers, 
            timeout=120
        )
        response.raise_for_status()
        
        result = response.json()
        summary = result.get("response", "Error: No response generated.")
        
        logger.info("Neural routing complete. Summary generated.", source="NLP")
        return f"[Summary]:\n{summary.strip()}"
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to route to Neural Engine: {e}", source="NLP")
        return f"[Error]: Inference routing failed. {e}"