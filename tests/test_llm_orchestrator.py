import pytest
import asyncio
from unittest.mock import MagicMock
import httpx

from src.llm_engine.orchestrator import LLMOrchestrator
from src.llm_engine.providers import (
    BaseLLMProvider,
    DeterministicSemanticProvider,
)


class MockFailingProvider(BaseLLMProvider):
    def name(self) -> str:
        return "MockFailingProvider"

    def is_configured(self) -> bool:
        return True

    async def extract_structured(self, prompt: str, schema_type: str):
        raise RuntimeError("Simulated cloud LLM outage")


class Mock429Provider(BaseLLMProvider):
    def __init__(self):
        self.call_count = 0

    def name(self) -> str:
        return "Mock429Provider"

    def is_configured(self) -> bool:
        return True

    async def extract_structured(self, prompt: str, schema_type: str):
        self.call_count += 1
        if self.call_count == 1:
            request = httpx.Request("POST", "http://test")
            response = httpx.Response(status_code=429, request=request)
            raise httpx.HTTPStatusError("Rate limited", request=request, response=response)
        return {"pricingModel": "PAID", "extra": "recovered_after_429"}


def test_deterministic_provider_extraction():
    provider = DeterministicSemanticProvider()

    async def _run():
        # Test startup employee extraction
        res_startup = await provider.extract_structured("Startup has a team size: 450 engineers.", "STARTUP")
        assert res_startup["employeeCount"] == 450

        # Test product pricing extraction
        res_prod = await provider.extract_structured("Try for free with our free tier, or upgrade to Pro.", "PRODUCT")
        assert res_prod["pricingModel"] == "FREEMIUM"

        # Test job extraction
        res_job = await provider.extract_structured("Looking for a Senior AI Researcher. Fully remote position.", "JOB")
        assert res_job["is_remote"] is True
        assert res_job["role_family"] == "Research"

    asyncio.run(_run())


def test_orchestrator_fallback_execution():
    orchestrator = LLMOrchestrator(
        providers=[MockFailingProvider(), DeterministicSemanticProvider()]
    )

    async def _run():
        res = await orchestrator.extract_with_fallback(
            "Company offers an Enterprise solution with contact sales pricing.",
            schema_type="PRODUCT"
        )
        assert res["pricingModel"] == "ENTERPRISE"

    asyncio.run(_run())


def test_orchestrator_429_backoff_recovery():
    mock_429 = Mock429Provider()
    orchestrator = LLMOrchestrator(
        providers=[mock_429, DeterministicSemanticProvider()]
    )
    orchestrator.backoff.base_delay = 0.01
    orchestrator.backoff.max_delay = 0.05

    async def _run():
        res = await orchestrator.extract_with_fallback(
            "Pricing is $50/mo paid.",
            schema_type="PRODUCT"
        )
        assert res["pricingModel"] == "PAID"
        assert mock_429.call_count == 2

    asyncio.run(_run())
