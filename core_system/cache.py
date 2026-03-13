# cache.py

import time
from threading import Lock


class SimpleCache:
    def __init__(self):
        self._cache = {}
        self._lock = Lock()

    def set(self, key, value, ttl=None):
        """Store a value with optional TTL (in seconds)."""
        with self._lock:
            expiry = time.time() + ttl if ttl else None
            self._cache[key] = (value, expiry)

    def get(self, key, default=None):
        """Retrieve a value if it hasn't expired."""
        with self._lock:
            item = self._cache.get(key)
            if item:
                value, expiry = item
                if expiry is None or time.time() < expiry:
                    return value
                else:
                    del self._cache[key]
        return default

    def exists(self, key):
        """Check if a key exists and is still valid."""
        return self.get(key) is not None

    def clear(self):
        """Clear the entire cache."""
        with self._lock:
            self._cache.clear()

    def delete(self, key):
        """Remove a single key."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]

    def cleanup(self):
        """Manually remove expired entries (optional use)."""
        with self._lock:
            now = time.time()
            keys_to_remove = [
                k for k, (_, exp) in self._cache.items() if exp and now > exp
            ]
            for k in keys_to_remove:
                del self._cache[k]


# Instantiate a global cache
cache = SimpleCache()
