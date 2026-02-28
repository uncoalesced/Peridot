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
