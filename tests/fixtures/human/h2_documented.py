"""HTTP retry helpers extracted from the connection pool rewrite (see #4471)."""

import time
from typing import Optional, Callable

DEFAULT_BACKOFF = 0.3
MAX_SLEEP = 120.0


class RetryPolicy:
    """Exponential backoff with jitter, capped at MAX_SLEEP.

    Mirrors urllib3's Retry semantics closely enough that callers can swap
    between the two, but without the deprecated `method_whitelist` handling
    that bit us in 2.28.
    """

    def __init__(self, total: int = 3, backoff: float = DEFAULT_BACKOFF) -> None:
        self.total = total
        self.backoff = backoff
        self._history: list = []

    def sleep_for(self, attempt: int) -> float:
        """Return seconds to sleep before ``attempt``.

        Attempt is 0-indexed; attempt 0 never sleeps.
        """
        if attempt <= 0:
            return 0.0
        return min(self.backoff * (2 ** (attempt - 1)), MAX_SLEEP)

    def run(self, fn: Callable, *args) -> Optional[object]:
        """Invoke ``fn`` until it stops raising or we exhaust ``self.total``."""
        last = None
        for attempt in range(self.total + 1):
            delay = self.sleep_for(attempt)
            if delay:
                time.sleep(delay)
            try:
                return fn(*args)
            except (IOError, OSError) as exc:
                last = exc
                self._history.append((attempt, repr(exc)))
        raise last
