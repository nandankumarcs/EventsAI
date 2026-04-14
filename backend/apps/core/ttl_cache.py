from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class CacheStats:
    hits: int
    misses: int
    sets: int
    deletes: int
    expirations: int


class TTLCache:
    def __init__(self, *, default_ttl_seconds: int = 86400, max_entries: int = 2048):
        self._default_ttl_seconds = default_ttl_seconds
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._store: dict[str, tuple[object, float]] = {}
        self._hits = 0
        self._misses = 0
        self._sets = 0
        self._deletes = 0
        self._expirations = 0

    def stats(self) -> CacheStats:
        with self._lock:
            return CacheStats(
                hits=self._hits,
                misses=self._misses,
                sets=self._sets,
                deletes=self._deletes,
                expirations=self._expirations,
            )

    def get(self, key: str) -> object | None:
        now = time.time()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            value, expires_at = entry
            if now >= expires_at:
                self._expirations += 1
                self._misses += 1
                self._store.pop(key, None)
                return None
            self._hits += 1
            return value

    def set(self, key: str, value: object, *, ttl_seconds: int | None = None) -> None:
        ttl = self._default_ttl_seconds if ttl_seconds is None else ttl_seconds
        expires_at = time.time() + ttl
        with self._lock:
            if key not in self._store and len(self._store) >= self._max_entries:
                oldest_key = min(self._store, key=lambda k: self._store[k][1])
                self._store.pop(oldest_key, None)
            self._store[key] = (value, expires_at)
            self._sets += 1

    def get_or_set(self, key: str, loader: Callable[[], Any], *, ttl_seconds: int | None = None) -> Any:
        cached = self.get(key)
        print(f"DEBUG: get_or_set: key={key}, cached={cached is not None}")
        if cached is not None:
            return cached
        value = loader()
        self.set(key, value, ttl_seconds=ttl_seconds)
        return value

    def delete(self, key: str) -> bool:
        with self._lock:
            removed = self._store.pop(key, None) is not None
            if removed:
                self._deletes += 1
            return removed

    def delete_prefix(self, prefix: str) -> int:
        with self._lock:
            keys = [key for key in self._store.keys() if key.startswith(prefix)]
            for key in keys:
                self._store.pop(key, None)
            if keys:
                self._deletes += len(keys)
            return len(keys)

    def clear(self) -> None:
        with self._lock:
            count = len(self._store)
            self._store.clear()
            if count:
                self._deletes += count


cache = TTLCache()
