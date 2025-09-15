from typing import Any, Optional
import hashlib
import json
import os
import pickle
from datetime import datetime, timedelta

class Cache:
    def __init__(self, cache_dir: str = ".cache", ttl_hours: int = 24):
        self.cache_dir = cache_dir
        self.ttl = timedelta(hours=ttl_hours)
        os.makedirs(cache_dir, exist_ok=True)

    def _get_cache_key(self, key: str) -> str:
        """Generate a cache key from input string"""
        return hashlib.md5(key.encode()).hexdigest()

    def _get_cache_path(self, key: str) -> str:
        """Get the full path for a cache file"""
        return os.path.join(self.cache_dir, f"{self._get_cache_key(key)}.pkl")

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if it exists and is not expired"""
        cache_path = self._get_cache_path(key)
        if not os.path.exists(cache_path):
            return None

        try:
            with open(cache_path, 'rb') as f:
                cached_data = pickle.load(f)

            # Check if cache is expired
            if datetime.now() - cached_data['timestamp'] > self.ttl:
                os.remove(cache_path)
                return None

            return cached_data['value']
        except:
            return None

    def set(self, key: str, value: Any):
        """Store value in cache with timestamp"""
        cache_path = self._get_cache_path(key)
        cache_data = {
            'timestamp': datetime.now(),
            'value': value
        }
        
        with open(cache_path, 'wb') as f:
            pickle.dump(cache_data, f)

# Create singleton instance
cache = Cache()