"""
Resilient Rate Limiting & Circuit Breaker Architecture.
Handles HTTP 429 Too Many Requests using Token Bucket and Exponential Backoff with Full Jitter.
"""

import asyncio
import time
import random
import logging
from typing import Optional, Callable, Any

logger = logging.getLogger("rate_limiter")


class FullJitterBackoff:
    """Implements AWS-recommended Full Jitter exponential backoff algorithm."""

    def __init__(self, base_delay: float = 1.0, max_delay: float = 60.0, max_retries: int = 5):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.max_retries = max_retries

    def calculate_delay(self, attempt: int) -> float:
        """Computes randomized delay with full jitter to avoid herd stampedes."""
        temp = min(self.max_delay, self.base_delay * (2 ** attempt))
        return random.uniform(0, temp)


class TokenBucket:
    """Async Token Bucket algorithm for proactive rate limiting."""

    def __init__(self, rate_per_second: float = 10.0, capacity: float = 20.0):
        self.rate = rate_per_second
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0):
        """Asynchronously waits until sufficient tokens are available in the bucket."""
        while True:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self.last_refill
                self.tokens = min(self.capacity, self.tokens + (elapsed * self.rate))
                self.last_refill = now

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return
                # Calculate required sleep
                needed = tokens - self.tokens
                wait_time = needed / self.rate

            await asyncio.sleep(min(wait_time, 1.0))


class CircuitBreaker:
    """Circuit breaker pattern to prevent thundering herds during sustained outages."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF-OPEN
        self.last_failure_time = 0.0

    def record_success(self):
        """Reset breaker state upon successful execution."""
        self.failure_count = 0
        self.state = "CLOSED"

    def record_failure(self):
        """Track failure and trip breaker if threshold exceeded."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(f"Circuit Breaker tripped to OPEN! Pausing requests for {self.recovery_timeout}s.")

    def can_execute(self) -> bool:
        """Determines if a request is allowed to proceed."""
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if (time.time() - self.last_failure_time) > self.recovery_timeout:
                self.state = "HALF-OPEN"
                logger.info("Circuit Breaker entering HALF-OPEN probe state.")
                return True
            return False
        if self.state == "HALF-OPEN":
            return True
        return False
