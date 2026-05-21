from cachetools import TTLCache
import hashlib
import json
from typing import Any, Dict

class SDKCache:
    """In-memory TTL cache for SDK requests to reduce API load."""
    def __init__(self, maxsize: int = 1000, ttl: int = 300):
        self.cache = TTLCache(maxsize=maxsize, ttl=ttl)
        
    def _generate_key(self, endpoint: str, params: Dict[str, Any]) -> str:
        param_str = json.dumps(params, sort_keys=True)
        return hashlib.md5(f"{endpoint}:{param_str}".encode()).hexdigest()
        
    def get(self, endpoint: str, params: Dict[str, Any]) -> Any:
        key = self._generate_key(endpoint, params)
        return self.cache.get(key)
        
    def set(self, endpoint: str, params: Dict[str, Any], data: Any):
        key = self._generate_key(endpoint, params)
        self.cache[key] = data
        
    def clear(self):
        self.cache.clear()
