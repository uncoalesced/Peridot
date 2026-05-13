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

import requests
from urllib.parse import urlparse

# --- FIXED IMPORT ---
from core_system.enhancedlogger import get_instance as get_logger

logger = get_logger()


def fetch_url_content(url):
    """
    Fetches the content of a URL securely.
    """
    try:
        logger.info(f"Fetching URL: {url}", source="NETWORK")

        headers = {"User-Agent": "iCould-Sovereign-OS/1.0"}

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        # Limit content size to prevent crashing memory
        content = response.text[:50000]
        return content

    except requests.exceptions.RequestException as e:
        logger.error(f"Network error fetching {url}: {e}", source="NETWORK")
        return f"Error fetching URL: {e}"
