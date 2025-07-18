from collections import OrderedDict
from typing import Any, Optional
import time
from threading import Lock


class LRUCache:
    """
    Thread-safe LRU cache with optional TTL (time-to-live) support.
    """
    def __init__(self, capacity: int = 100, ttl: Optional[int] = None):
        """
        Initialize the LRU cache.
        
        Args:
            capacity: Maximum number of items to store
            ttl: Time-to-live in seconds (None for no expiration)
        """
        self.capacity = capacity
        self.ttl = ttl
        self.cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self.lock = Lock()

    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve an item from the cache.
        
        Args:
            key: The cache key
            
        Returns:
            The cached value or None if not found/expired
        """
        with self.lock:
            if key not in self.cache:
                return None
            
            value, timestamp = self.cache[key]
            
            # Check if item has expired
            if self.ttl and time.time() - timestamp > self.ttl:
                del self.cache[key]
                return None
            
            # Move to end to mark as recently used
            self.cache.move_to_end(key)
            return value

    def put(self, key: str, value: Any) -> None:
        """
        Store an item in the cache.
        
        Args:
            key: The cache key
            value: The value to cache
        """
        with self.lock:
            # Remove existing key to re-insert at end
            if key in self.cache:
                del self.cache[key]
            
            # Add new item with timestamp
            self.cache[key] = (value, time.time())
            
            # Evict least recently used if capacity exceeded
            if len(self.cache) > self.capacity:
                self.cache.popitem(last=False)

    def clear(self) -> None:
        """Clear all items from the cache."""
        with self.lock:
            self.cache.clear()

    def size(self) -> int:
        """Get the current number of items in the cache."""
        with self.lock:
            return len(self.cache)