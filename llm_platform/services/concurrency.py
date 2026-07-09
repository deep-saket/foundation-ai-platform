"""Concurrency tracking for intelligent scale-out routing."""

from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)

class ConcurrencyTracker:
    """Track active requests per deployment."""

    def __init__(self) -> None:
        self._active: dict[str, int] = {}
        self._lock = threading.Lock()

    def get_active_requests(self, deployment_id: str) -> int:
        """Get the number of active requests for a deployment."""
        with self._lock:
            return self._active.get(deployment_id, 0)

    def increment(self, deployment_id: str) -> None:
        """Increment the active request counter for a deployment."""
        with self._lock:
            current = self._active.get(deployment_id, 0)
            self._active[deployment_id] = current + 1
            
    def decrement(self, deployment_id: str) -> None:
        """Decrement the active request counter for a deployment."""
        with self._lock:
            current = self._active.get(deployment_id, 0)
            if current > 0:
                self._active[deployment_id] = current - 1
            else:
                self._active[deployment_id] = 0

    def get_all(self) -> dict[str, int]:
        """Get a copy of the concurrency map."""
        with self._lock:
            return dict(self._active)
