"""
Base Asynchronous Crawler with Connection Pooling, Anti-Bot Headers,
and Resilient Retry Handling.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
import httpx

from ..anti_bot.stealth import StealthHeaders
from ..llm_engine.rate_limiter import FullJitterBackoff

logger = logging.getLogger("base_crawler")


class BaseAsyncCrawler:
    """Enterprise-grade async HTTP crawler foundation."""

    def __init__(
        self,
        concurrency_limit: int = 20,
        request_timeout: float = 20.0,
        max_retries: int = 3,
    ):
        self.concurrency_limit = concurrency_limit
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.timeout = httpx.Timeout(request_timeout, connect=10.0)
        self.backoff = FullJitterBackoff(base_delay=1.0, max_delay=15.0, max_retries=max_retries)
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        """Lazy initialization of high-performance HTTP/2 async client."""
        if self._client is None or self._client.is_closed:
            limits = httpx.Limits(max_keepalive_connections=50, max_connections=100)
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                limits=limits,
                follow_redirects=True,
            )
        return self._client

    async def fetch(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        referer: Optional[str] = None,
    ) -> httpx.Response:
        """Fetches a URL with concurrency bounding, stealth headers, and jittered retries."""
        client = await self.get_client()
        req_headers = StealthHeaders.get_headers(referer=referer)
        if headers:
            req_headers.update(headers)

        async with self.semaphore:
            for attempt in range(self.backoff.max_retries):
                try:
                    resp = await client.get(url, headers=req_headers)
                    if resp.status_code == 429:
                        delay = self.backoff.calculate_delay(attempt)
                        logger.warning(f"429 rate limit on {url}. Backing off for {delay:.2f}s...")
                        await asyncio.sleep(delay)
                        continue
                    resp.raise_for_status()
                    return resp
                except (httpx.RequestError, httpx.HTTPStatusError) as e:
                    if attempt == self.backoff.max_retries - 1:
                        logger.error(f"Failed to fetch {url} after {self.backoff.max_retries} attempts: {e}")
                        raise
                    delay = self.backoff.calculate_delay(attempt)
                    await asyncio.sleep(delay)

            raise httpx.RequestError(f"Failed after {self.backoff.max_retries} attempts", request=None)

    async def fetch_json(self, url: str, headers: Optional[Dict[str, str]] = None) -> Any:
        """Fetches and parses JSON payload directly."""
        resp = await self.fetch(url, headers=headers)
        return resp.json()

    async def close(self):
        """Closes the underlying HTTP client session."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
