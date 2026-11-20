import pytest
import asyncio
from src.llm_engine.orchestrator import LLMOrchestrator
from src.llm_engine.providers import DeterministicSemanticProvider


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
    orchestrator = LLMOrchestrator()

    async def _run():
        res = await orchestrator.extract_with_fallback(
            "Company offers an Enterprise solution with contact sales pricing.",
            schema_type="PRODUCT"
        )
        assert res["pricingModel"] == "ENTERPRISE"

    asyncio.run(_run())
