"""A small in-process rate limiter for the public outcome endpoint.

Sliding window per key (the caller's IP). Good enough for one Fly machine and
a single operator's CRM; a shared store would be needed before scaling out.
"""

from __future__ import annotations

import threading
import time
from collections import deque


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float) -> None:
        self._limit = limit
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        with self._lock:
            q = self._hits.setdefault(key, deque())
            cutoff = now - self._window
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) >= self._limit:
                return False
            q.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
