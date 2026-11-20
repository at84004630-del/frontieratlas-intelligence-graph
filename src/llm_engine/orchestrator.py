"""
Multi-Tier LLM Orchestration Engine.
Orchestrates Gemini Flash -> Groq Llama 3 -> DeepSeek -> Deterministic Semantic Engine
with automated 413 avoidance, 429 backoff with full jitter, and circuit breaking.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
import httpx

from .chunker import IntelligentChunker
from .rate_limiter import FullJitterBackoff, CircuitBreaker, TokenBucket
from .providers import (
    BaseLLMProvider,
    GeminiFlashProvider,
    GroqLlama3Provider,
    DeepSeekProvider,
    DeterministicSemanticProvider,
)

logger = logging.getLogger("llm_orchestrator")


class LLMOrchestrator:
    """Production-grade multi-tier LLM fallback orchestrator."""

    def __init__(
        self,
        providers: Optional[List[BaseLLMProvider]] = None,
        max_tokens_per_payload: int = 4000,
        enable_rate_limiting: bool = True,
    ):
        self.chunker = IntelligentChunker(max_tokens=max_tokens_per_payload)
        self.backoff = FullJitterBackoff(base_delay=1.0, max_delay=30.0, max_retries=3)
        self.circuit_breaker = CircuitBreaker(failure_threshold=4, recovery_timeout=20.0)
        self.token_bucket = TokenBucket(rate_per_second=10.0, capacity=20.0) if enable_rate_limiting else None

        # Build fallback chain: Gemini -> Groq -> DeepSeek -> Deterministic
        self.providers: List[BaseLLMProvider] = providers or [
            GeminiFlashProvider(),
            GroqLlama3Provider(),
            DeepSeekProvider(),
            DeterministicSemanticProvider(),
        ]

    async def extract_with_fallback(
        self,
        raw_text_or_html: str,
        schema_type: str,
        is_html: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes payload truncation and attempts extraction across the multi-tier provider chain.
        Guarantees:
        1. Never throws 413 (content is chunked/truncated prior to dispatch).
        2. Handles 429 with exponential backoff & jitter.
        3. Cascades to next tier if a provider is unconfigured, rate-limited, or fails.
        """
        # Step 1: Intelligent Truncation (prevents 413 Payload Too Large)
        safe_prompt = self.chunker.truncate_to_dense_summary(raw_text_or_html) if is_html else raw_text_or_html[:15000]

        last_error = None

        for provider in self.providers:
            if not provider.is_configured():
                logger.debug(f"Skipping {provider.name()} (not configured)")
                continue

            # Circuit breaker check for remote APIs
            if not isinstance(provider, DeterministicSemanticProvider) and not self.circuit_breaker.can_execute():
                logger.warning(f"Circuit breaker OPEN. Skipping cloud provider {provider.name()}")
                continue

            for attempt in range(self.backoff.max_retries):
                try:
                    # Token bucket rate limiting
                    if self.token_bucket and not isinstance(provider, DeterministicSemanticProvider):
                        await self.token_bucket.acquire(1.0)

                    # Dispatch extraction
                    result = await provider.extract_structured(safe_prompt, schema_type)
                    if not isinstance(provider, DeterministicSemanticProvider):
                        self.circuit_breaker.record_success()

                    logger.debug(f"Successfully extracted with {provider.name()}")
                    return result

                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        # Rate limit encounter: sleep with full jitter
                        delay = self.backoff.calculate_delay(attempt)
                        logger.warning(f"{provider.name()} 429 Too Many Requests! Retrying in {delay:.2f}s (attempt {attempt+1}/{self.backoff.max_retries})")
                        await asyncio.sleep(delay)
                        continue
                    elif e.response.status_code == 413:
                        # Context window overflow: aggressively re-truncate
                        logger.warning(f"{provider.name()} 413 Payload Too Large! Shrinking payload by 50%...")
                        safe_prompt = safe_prompt[: len(safe_prompt) // 2]
                        continue
                    else:
                        logger.error(f"{provider.name()} HTTP error: {e}")
                        break

                except Exception as e:
                    logger.warning(f"{provider.name()} failed with error: {e}")
                    last_error = e
                    break

            # If this provider failed all retries, record circuit failure and try next tier
            if not isinstance(provider, DeterministicSemanticProvider):
                self.circuit_breaker.record_failure()
            logger.info(f"Cascading fallback to next provider after {provider.name()} exhaustion...")

        # If all cloud providers failed or are unconfigured, deterministic provider is the safety net
        logger.info("Executing deterministic semantic fallback...")
        fallback = DeterministicSemanticProvider()
        return await fallback.extract_structured(safe_prompt, schema_type)
