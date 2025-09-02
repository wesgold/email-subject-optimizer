import os
import redis.asyncio as redis
from diskcache import Cache
from typing import Optional, Union
import json
import hashlib

class CacheManager:
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL")
        self.redis_client: Optional[redis.Redis] = None
        self.disk_cache = Cache('./data/cache')
        
    async def initialize(self):
        if self.redis_url:
            try:
                self.redis_client = redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                await self.redis_client.ping()
                print("Redis connected successfully")
            except Exception as e:
                print(f"Redis connection failed, falling back to disk cache: {e}")
                self.redis_client = None
    
    def _generate_cache_key(self, content: str) -> str:
        """Generate SHA256 hash for cache key"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    async def get(self, key: str) -> Optional[dict]:
        cache_key = self._generate_cache_key(key)
        
        if self.redis_client:
            try:
                result = await self.redis_client.get(cache_key)
                return json.loads(result) if result else None
            except Exception:
                pass  # Fall back to disk cache
        
        # Disk cache fallback
        return self.disk_cache.get(cache_key)
    
    async def set(self, key: str, value: dict, ttl: int = 3600):
        cache_key = self._generate_cache_key(key)
        
        if self.redis_client:
            try:
                await self.redis_client.setex(cache_key, ttl, json.dumps(value))
                return
            except Exception:
                pass  # Fall back to disk cache
        
        # Disk cache fallback
        self.disk_cache.set(cache_key, value, expire=ttl)

# Global cache instance
cache_manager = CacheManager()