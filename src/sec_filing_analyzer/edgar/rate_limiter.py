"""Simple thread-safe rate limiter for EDGAR requests.

The SEC caps automated access at 10 requests/second
(https://www.sec.gov/os/accessing-edgar-data). We enforce a minimum
interval between requests; the default stays well below the cap.
"""

from __future__ import annotations

import threading
import time


class RateLimiter:
    def __init__(self, max_per_second: float = 5.0, clock=time.monotonic, sleep=time.sleep):
        if max_per_second <= 0:
            raise ValueError("max_per_second must be positive")
        self.min_interval = 1.0 / min(max_per_second, 10.0)
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def acquire(self) -> None:
        """Block until the next request is allowed."""
        with self._lock:
            now = self._clock()
            wait = self._next_allowed - now
            if wait > 0:
                self._sleep(wait)
                now = self._clock()
            self._next_allowed = max(self._next_allowed, now) + self.min_interval
