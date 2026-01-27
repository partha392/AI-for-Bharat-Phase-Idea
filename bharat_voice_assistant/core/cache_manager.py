"""
Cache management module for the Bharat Voice Assistant.

This module implements local caching for frequently accessed information
to reduce data usage and enable offline functionality. Supports multiple
cache types including in-memory, file-based, and persistent storage.

Implements Requirement 5.3: Local caching for frequently accessed information.
"""

import asyncio
import json
import pickle
import time
import hashlib
import sqlite3
from typing import Dict, Any, Optional, List, Union, Callable
from dataclasses import dataclass, asdict
from pathlib import Path
from enum import Enum
import threading
from contextlib import asynccontextmanager

from bharat_voice_assistant.core.config import config
from bharat_voice_assistant.core.logging import get_logger
from bharat_voice_assistant.core.exceptions import CacheError

logger = get_logger(__name__)


class CacheType(Enum):
    """Types of cache storage."""
    MEMORY = "memory"
    FILE = "file"
    DATABASE = "database"
    HYBRID = "hybrid"


class CachePolicy(Enum):
    """Cache eviction policies."""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    TTL = "ttl"  # Time To Live
    FIFO = "fifo"  # First In First Out


@dataclass
class CacheEntry:
    """Represents a cache entry with metadata."""
    key: str
    value: Any
    created_at: float
    last_accessed: float
    access_count: int
    ttl_seconds: Optional[int] = None
    size_bytes: int = 0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        if self.ttl_seconds is None:
            return False
        return time.time() - self.created_at > self.ttl_seconds
    
    def update_access(self):
        """Update access statistics."""
        self.last_accessed = time.time()
        self.access_count += 1


@dataclass
class CacheStats:
    """Cache performance statistics."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_entries: int = 0
    total_size_bytes: int = 0
    hit_rate: float = 0.0
    
    def update_hit_rate(self):
        """Update the hit rate calculation."""
        total_requests = self.hits + self.misses
        self.hit_rate = self.hits / total_requests if total_requests > 0 else 0.0


class CacheManager:
    """
    Manages local caching for frequently accessed information.
    
    Implements Requirement 5.3: Local caching for frequently accessed information.
    """
    
    def __init__(self, cache_type: CacheType = CacheType.HYBRID,
                 max_memory_size_mb: int = 100,
                 max_file_size_mb: int = 500,
                 cache_dir: str = "cache",
                 default_ttl_seconds: int = 3600):
        """
        Initialize the cache manager.
        
        Args:
            cache_type: Type of cache storage to use
            max_memory_size_mb: Maximum memory cache size in MB
            max_file_size_mb: Maximum file cache size in MB
            cache_dir: Directory for file-based cache
            default_ttl_seconds: Default TTL for cache entries
        """
        self.cache_type = cache_type
        self.max_memory_size = max_memory_size_mb * 1024 * 1024  # Convert to bytes
        self.max_file_size = max_file_size_mb * 1024 * 1024
        self.default_ttl = default_ttl_seconds
        
        # Cache storage
        self.memory_cache: Dict[str, CacheEntry] = {}
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Database cache
        self.db_path = self.cache_dir / "cache.db"
        self._init_database()
        
        # Statistics and management
        self.stats = CacheStats()
        self._lock = threading.RLock()
        
        # Background cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        # Cache policies
        self.memory_policy = CachePolicy.LRU
        self.file_policy = CachePolicy.TTL
        
        logger.info(f"CacheManager initialized with {cache_type.value} storage")
    
    async def start(self):
        """Start the cache manager background tasks."""
        self._cleanup_task = asyncio.create_task(self._cleanup_expired_entries())
        logger.info("CacheManager started")
    
    async def stop(self):
        """Stop the cache manager and cleanup resources."""
        self._shutdown_event.set()
        if self._cleanup_task:
            self._cleanup_task.cancel()
        
        # Persist memory cache to disk if using hybrid mode
        if self.cache_type == CacheType.HYBRID:
            await self._persist_memory_cache()
        
        logger.info("CacheManager stopped")
    
    async def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from cache.
        
        Args:
            key: Cache key
            default: Default value if key not found
            
        Returns:
            Cached value or default
        """
        try:
            with self._lock:
                # Try memory cache first
                if key in self.memory_cache:
                    entry = self.memory_cache[key]
                    if not entry.is_expired():
                        entry.update_access()
                        self.stats.hits += 1
                        self.stats.update_hit_rate()
                        logger.debug(f"Cache hit (memory): {key}")
                        return entry.value
                    else:
                        # Remove expired entry
                        del self.memory_cache[key]
                
                # Try file cache
                if self.cache_type in [CacheType.FILE, CacheType.HYBRID]:
                    file_value = await self._get_from_file(key)
                    if file_value is not None:
                        # Load into memory cache for faster access
                        await self._store_in_memory(key, file_value, self.default_ttl)
                        self.stats.hits += 1
                        self.stats.update_hit_rate()
                        logger.debug(f"Cache hit (file): {key}")
                        return file_value
                
                # Try database cache
                if self.cache_type in [CacheType.DATABASE, CacheType.HYBRID]:
                    db_value = await self._get_from_database(key)
                    if db_value is not None:
                        # Load into memory cache for faster access
                        await self._store_in_memory(key, db_value, self.default_ttl)
                        self.stats.hits += 1
                        self.stats.update_hit_rate()
                        logger.debug(f"Cache hit (database): {key}")
                        return db_value
                
                # Cache miss
                self.stats.misses += 1
                self.stats.update_hit_rate()
                logger.debug(f"Cache miss: {key}")
                return default
                
        except Exception as e:
            logger.error(f"Error getting cache entry {key}: {e}")
            return default
    
    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None,
                  metadata: Dict[str, Any] = None) -> bool:
        """
        Set a value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time to live in seconds
            metadata: Optional metadata
            
        Returns:
            True if successfully cached, False otherwise
        """
        try:
            ttl = ttl_seconds or self.default_ttl
            
            with self._lock:
                # Store in memory cache
                if self.cache_type in [CacheType.MEMORY, CacheType.HYBRID]:
                    await self._store_in_memory(key, value, ttl, metadata)
                
                # Store in file cache
                if self.cache_type in [CacheType.FILE, CacheType.HYBRID]:
                    await self._store_in_file(key, value, ttl, metadata)
                
                # Store in database cache
                if self.cache_type in [CacheType.DATABASE, CacheType.HYBRID]:
                    await self._store_in_database(key, value, ttl, metadata)
                
                logger.debug(f"Cache set: {key}")
                return True
                
        except Exception as e:
            logger.error(f"Error setting cache entry {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Delete a cache entry.
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if deleted, False if not found
        """
        try:
            deleted = False
            
            with self._lock:
                # Delete from memory cache
                if key in self.memory_cache:
                    del self.memory_cache[key]
                    deleted = True
                
                # Delete from file cache
                file_path = self._get_file_path(key)
                if file_path.exists():
                    file_path.unlink()
                    deleted = True
                
                # Delete from database cache
                await self._delete_from_database(key)
                deleted = True
                
                if deleted:
                    logger.debug(f"Cache deleted: {key}")
                
                return deleted
                
        except Exception as e:
            logger.error(f"Error deleting cache entry {key}: {e}")
            return False
    
    async def clear(self, pattern: Optional[str] = None) -> int:
        """
        Clear cache entries, optionally matching a pattern.
        
        Args:
            pattern: Optional pattern to match keys (simple wildcard support)
            
        Returns:
            Number of entries cleared
        """
        try:
            cleared_count = 0
            
            with self._lock:
                if pattern is None:
                    # Clear all
                    cleared_count += len(self.memory_cache)
                    self.memory_cache.clear()
                    
                    # Clear file cache
                    for file_path in self.cache_dir.glob("*.cache"):
                        file_path.unlink()
                        cleared_count += 1
                    
                    # Clear database cache
                    cleared_count += await self._clear_database()
                    
                else:
                    # Clear matching pattern
                    keys_to_delete = []
                    for key in self.memory_cache.keys():
                        if self._matches_pattern(key, pattern):
                            keys_to_delete.append(key)
                    
                    for key in keys_to_delete:
                        await self.delete(key)
                        cleared_count += 1
                
                logger.info(f"Cache cleared: {cleared_count} entries")
                return cleared_count
                
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return 0
    
    async def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        with self._lock:
            self.stats.total_entries = len(self.memory_cache)
            self.stats.total_size_bytes = sum(
                entry.size_bytes for entry in self.memory_cache.values()
            )
            return self.stats
    
    async def get_cached_schemes(self, user_profile: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Get cached government schemes, optionally filtered by user profile.
        
        Args:
            user_profile: Optional user profile for filtering
            
        Returns:
            List of cached schemes
        """
        try:
            # Create cache key based on user profile
            if user_profile:
                profile_hash = hashlib.md5(
                    json.dumps(user_profile, sort_keys=True).encode()
                ).hexdigest()
                cache_key = f"schemes_filtered_{profile_hash}"
            else:
                cache_key = "schemes_all"
            
            cached_schemes = await self.get(cache_key)
            if cached_schemes is not None:
                logger.debug(f"Retrieved {len(cached_schemes)} cached schemes")
                return cached_schemes
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting cached schemes: {e}")
            return []
    
    async def cache_schemes(self, schemes: List[Dict[str, Any]], 
                          user_profile: Dict[str, Any] = None,
                          ttl_seconds: int = 3600) -> bool:
        """
        Cache government schemes.
        
        Args:
            schemes: List of schemes to cache
            user_profile: Optional user profile for filtered caching
            ttl_seconds: Time to live for cached schemes
            
        Returns:
            True if successfully cached
        """
        try:
            # Create cache key based on user profile
            if user_profile:
                profile_hash = hashlib.md5(
                    json.dumps(user_profile, sort_keys=True).encode()
                ).hexdigest()
                cache_key = f"schemes_filtered_{profile_hash}"
            else:
                cache_key = "schemes_all"
            
            metadata = {
                "type": "schemes",
                "count": len(schemes),
                "user_profile_hash": profile_hash if user_profile else None,
                "cached_at": time.time()
            }
            
            success = await self.set(cache_key, schemes, ttl_seconds, metadata)
            if success:
                logger.info(f"Cached {len(schemes)} schemes with key {cache_key}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error caching schemes: {e}")
            return False
    
    async def get_cached_user_data(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached user data.
        
        Args:
            user_id: User identifier
            
        Returns:
            Cached user data or None
        """
        cache_key = f"user_data_{user_id}"
        return await self.get(cache_key)
    
    async def cache_user_data(self, user_id: str, user_data: Dict[str, Any],
                            ttl_seconds: int = 1800) -> bool:
        """
        Cache user data.
        
        Args:
            user_id: User identifier
            user_data: User data to cache
            ttl_seconds: Time to live (default 30 minutes)
            
        Returns:
            True if successfully cached
        """
        cache_key = f"user_data_{user_id}"
        metadata = {
            "type": "user_data",
            "user_id": user_id,
            "cached_at": time.time()
        }
        return await self.set(cache_key, user_data, ttl_seconds, metadata)
    
    async def get_cached_responses(self, intent: str, language: str = "hi") -> Optional[List[str]]:
        """
        Get cached response templates.
        
        Args:
            intent: Intent identifier
            language: Language code
            
        Returns:
            List of cached response templates or None
        """
        cache_key = f"responses_{intent}_{language}"
        return await self.get(cache_key)
    
    async def cache_responses(self, intent: str, language: str, 
                            responses: List[str], ttl_seconds: int = 7200) -> bool:
        """
        Cache response templates.
        
        Args:
            intent: Intent identifier
            language: Language code
            responses: List of response templates
            ttl_seconds: Time to live (default 2 hours)
            
        Returns:
            True if successfully cached
        """
        cache_key = f"responses_{intent}_{language}"
        metadata = {
            "type": "responses",
            "intent": intent,
            "language": language,
            "count": len(responses),
            "cached_at": time.time()
        }
        return await self.set(cache_key, responses, ttl_seconds, metadata)
    
    def _init_database(self):
        """Initialize SQLite database for persistent cache."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS cache_entries (
                        key TEXT PRIMARY KEY,
                        value BLOB,
                        created_at REAL,
                        last_accessed REAL,
                        access_count INTEGER,
                        ttl_seconds INTEGER,
                        size_bytes INTEGER,
                        metadata TEXT
                    )
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_created_at ON cache_entries(created_at)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_last_accessed ON cache_entries(last_accessed)
                """)
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error initializing cache database: {e}")
    
    async def _store_in_memory(self, key: str, value: Any, ttl_seconds: int,
                             metadata: Dict[str, Any] = None):
        """Store entry in memory cache."""
        # Calculate size
        try:
            size_bytes = len(pickle.dumps(value))
        except:
            size_bytes = len(str(value).encode())
        
        # Check if we need to evict entries
        await self._evict_if_needed(size_bytes)
        
        # Create cache entry
        entry = CacheEntry(
            key=key,
            value=value,
            created_at=time.time(),
            last_accessed=time.time(),
            access_count=1,
            ttl_seconds=ttl_seconds,
            size_bytes=size_bytes,
            metadata=metadata or {}
        )
        
        self.memory_cache[key] = entry
    
    async def _store_in_file(self, key: str, value: Any, ttl_seconds: int,
                           metadata: Dict[str, Any] = None):
        """Store entry in file cache."""
        try:
            file_path = self._get_file_path(key)
            
            cache_data = {
                "value": value,
                "created_at": time.time(),
                "ttl_seconds": ttl_seconds,
                "metadata": metadata or {}
            }
            
            with open(file_path, 'wb') as f:
                pickle.dump(cache_data, f)
                
        except Exception as e:
            logger.error(f"Error storing in file cache: {e}")
    
    async def _store_in_database(self, key: str, value: Any, ttl_seconds: int,
                               metadata: Dict[str, Any] = None):
        """Store entry in database cache."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                value_blob = pickle.dumps(value)
                metadata_json = json.dumps(metadata or {})
                
                conn.execute("""
                    INSERT OR REPLACE INTO cache_entries 
                    (key, value, created_at, last_accessed, access_count, ttl_seconds, size_bytes, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    key, value_blob, time.time(), time.time(), 1,
                    ttl_seconds, len(value_blob), metadata_json
                ))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error storing in database cache: {e}")
    
    async def _get_from_file(self, key: str) -> Any:
        """Get entry from file cache."""
        try:
            file_path = self._get_file_path(key)
            if not file_path.exists():
                return None
            
            with open(file_path, 'rb') as f:
                cache_data = pickle.load(f)
            
            # Check if expired
            if cache_data.get("ttl_seconds"):
                age = time.time() - cache_data["created_at"]
                if age > cache_data["ttl_seconds"]:
                    file_path.unlink()  # Remove expired file
                    return None
            
            return cache_data["value"]
            
        except Exception as e:
            logger.error(f"Error getting from file cache: {e}")
            return None
    
    async def _get_from_database(self, key: str) -> Any:
        """Get entry from database cache."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT value, created_at, ttl_seconds FROM cache_entries WHERE key = ?
                """, (key,))
                row = cursor.fetchone()
                
                if row is None:
                    return None
                
                value_blob, created_at, ttl_seconds = row
                
                # Check if expired
                if ttl_seconds and (time.time() - created_at > ttl_seconds):
                    conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                    conn.commit()
                    return None
                
                # Update access statistics
                conn.execute("""
                    UPDATE cache_entries 
                    SET last_accessed = ?, access_count = access_count + 1
                    WHERE key = ?
                """, (time.time(), key))
                conn.commit()
                
                return pickle.loads(value_blob)
                
        except Exception as e:
            logger.error(f"Error getting from database cache: {e}")
            return None
    
    async def _delete_from_database(self, key: str):
        """Delete entry from database cache."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                conn.commit()
        except Exception as e:
            logger.error(f"Error deleting from database cache: {e}")
    
    async def _clear_database(self) -> int:
        """Clear all entries from database cache."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM cache_entries")
                count = cursor.fetchone()[0]
                conn.execute("DELETE FROM cache_entries")
                conn.commit()
                return count
        except Exception as e:
            logger.error(f"Error clearing database cache: {e}")
            return 0
    
    def _get_file_path(self, key: str) -> Path:
        """Get file path for cache key."""
        # Create safe filename from key
        safe_key = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{safe_key}.cache"
    
    async def _evict_if_needed(self, new_entry_size: int):
        """Evict entries if memory limit would be exceeded."""
        current_size = sum(entry.size_bytes for entry in self.memory_cache.values())
        
        if current_size + new_entry_size > self.max_memory_size:
            # Evict based on policy
            if self.memory_policy == CachePolicy.LRU:
                await self._evict_lru(new_entry_size)
            elif self.memory_policy == CachePolicy.LFU:
                await self._evict_lfu(new_entry_size)
            elif self.memory_policy == CachePolicy.TTL:
                await self._evict_expired()
    
    async def _evict_lru(self, needed_size: int):
        """Evict least recently used entries."""
        # Sort by last accessed time
        sorted_entries = sorted(
            self.memory_cache.items(),
            key=lambda x: x[1].last_accessed
        )
        
        freed_size = 0
        for key, entry in sorted_entries:
            if freed_size >= needed_size:
                break
            
            freed_size += entry.size_bytes
            del self.memory_cache[key]
            self.stats.evictions += 1
    
    async def _evict_lfu(self, needed_size: int):
        """Evict least frequently used entries."""
        # Sort by access count
        sorted_entries = sorted(
            self.memory_cache.items(),
            key=lambda x: x[1].access_count
        )
        
        freed_size = 0
        for key, entry in sorted_entries:
            if freed_size >= needed_size:
                break
            
            freed_size += entry.size_bytes
            del self.memory_cache[key]
            self.stats.evictions += 1
    
    async def _evict_expired(self):
        """Evict expired entries."""
        expired_keys = []
        for key, entry in self.memory_cache.items():
            if entry.is_expired():
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.memory_cache[key]
            self.stats.evictions += 1
    
    async def _persist_memory_cache(self):
        """Persist memory cache to disk."""
        try:
            for key, entry in self.memory_cache.items():
                if not entry.is_expired():
                    await self._store_in_file(
                        key, entry.value, entry.ttl_seconds, entry.metadata
                    )
            logger.info("Memory cache persisted to disk")
        except Exception as e:
            logger.error(f"Error persisting memory cache: {e}")
    
    def _matches_pattern(self, key: str, pattern: str) -> bool:
        """Simple wildcard pattern matching."""
        if '*' not in pattern:
            return key == pattern
        
        # Simple wildcard support
        pattern_parts = pattern.split('*')
        if len(pattern_parts) == 2:
            prefix, suffix = pattern_parts
            return key.startswith(prefix) and key.endswith(suffix)
        
        return False
    
    async def _cleanup_expired_entries(self):
        """Background task to cleanup expired entries."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                
                # Cleanup memory cache
                await self._evict_expired()
                
                # Cleanup file cache
                for file_path in self.cache_dir.glob("*.cache"):
                    try:
                        with open(file_path, 'rb') as f:
                            cache_data = pickle.load(f)
                        
                        if cache_data.get("ttl_seconds"):
                            age = time.time() - cache_data["created_at"]
                            if age > cache_data["ttl_seconds"]:
                                file_path.unlink()
                    except:
                        # Remove corrupted files
                        file_path.unlink()
                
                # Cleanup database cache
                try:
                    with sqlite3.connect(self.db_path) as conn:
                        conn.execute("""
                            DELETE FROM cache_entries 
                            WHERE ttl_seconds IS NOT NULL 
                            AND (? - created_at) > ttl_seconds
                        """, (time.time(),))
                        conn.commit()
                except Exception as e:
                    logger.error(f"Error cleaning up database cache: {e}")
                
                logger.debug("Cache cleanup completed")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cache cleanup: {e}")


# Global cache manager instance
cache_manager = CacheManager()