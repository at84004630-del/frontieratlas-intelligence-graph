"""
LLM Provider Abstractions for Multi-Tier Extraction Engine.
Supports Gemini Flash, Groq Llama 3, DeepSeek, and Deterministic Semantic Parsing.
"""

import os
import json
import re
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

import httpx

from ..utils.date_normalizer import DateNormalizer
from ..entity_resolution.normalizer import EntityNormalizer

logger = logging.getLogger("llm_providers")


class BaseLLMProvider(ABC):
    """Abstract interface for all LLM extraction providers."""

    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        pass

    @abstractmethod
    async def extract_structured(self, prompt: str, schema_type: str) -> Dict[str, Any]:
        """Processes unstructured prompt and outputs schema-aligned JSON dict."""
        pass


class GeminiFlashProvider(BaseLLMProvider):
    """Tier 1: Google Gemini Flash via REST/GenAI API."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-1.5-flash"):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self.model = model
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"

    def name(self) -> str:
        return f"Gemini Flash ({self.model})"

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def extract_structured(self, prompt: str, schema_type: str) -> Dict[str, Any]:
        if not self.is_configured():
            raise ValueError("GEMINI_API_KEY not configured.")

        system_instruction = (
            f"You are an expert data intelligence extraction engine. "
            f"Extract the requested data strictly conforming to JSON for schema: {schema_type}. "
            f"Do not hallucinate URLs or dates. Return ONLY valid JSON."
        )

        payload = {
            "contents": [{"parts": [{"text": f"{system_instruction}\n\nContent:\n{prompt}"}]}],
            "generationConfig": {
                "temperature": 0.1,
                "response_mime_type": "application/json"
            }
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{self.url}?key={self.api_key}", json=payload)
            if resp.status_code == 429:
                raise httpx.HTTPStatusError("Gemini Rate Limit Exceeded", request=resp.request, response=resp)
            if resp.status_code == 413:
                raise httpx.HTTPStatusError("Gemini Payload Too Large", request=resp.request, response=resp)
            resp.raise_for_status()

            data = resp.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(raw_text)


class GroqLlama3Provider(BaseLLMProvider):
    """Tier 2: Groq Llama 3 (e.g. llama-3.3-70b-versatile / llama-3.1-8b-instant)."""

    def __init__(self, api_key: Optional[str] = None, model: str = "llama-3.3-70b-versatile"):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self.model = model
        self.url = "https://api.groq.com/openai/v1/chat/completions"

    def name(self) -> str:
        return f"Groq ({self.model})"

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def extract_structured(self, prompt: str, schema_type: str) -> Dict[str, Any]:
        if not self.is_configured():
            raise ValueError("GROQ_API_KEY not configured.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": f"Extract structured data strictly as JSON conforming to schema: {schema_type}."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(self.url, headers=headers, json=payload)
            if resp.status_code == 429:
                raise httpx.HTTPStatusError("Groq Rate Limit Exceeded", request=resp.request, response=resp)
            if resp.status_code == 413:
                raise httpx.HTTPStatusError("Groq Payload Too Large", request=resp.request, response=resp)
            resp.raise_for_status()

            data = resp.json()
            raw_text = data["choices"][0]["message"]["content"]
            return json.loads(raw_text)


class DeepSeekProvider(BaseLLMProvider):
    """Tier 3: DeepSeek API (deepseek-chat)."""

    def __init__(self, api_key: Optional[str] = None, model: str = "deepseek-chat"):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        self.model = model
        self.url = "https://api.deepseek.com/chat/completions"

    def name(self) -> str:
        return f"DeepSeek ({self.model})"

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def extract_structured(self, prompt: str, schema_type: str) -> Dict[str, Any]:
        if not self.is_configured():
            raise ValueError("DEEPSEEK_API_KEY not configured.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": f"Extract structured data strictly as JSON conforming to schema: {schema_type}."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(self.url, headers=headers, json=payload)
            if resp.status_code == 429:
                raise httpx.HTTPStatusError("DeepSeek Rate Limit Exceeded", request=resp.request, response=resp)
            if resp.status_code == 413:
                raise httpx.HTTPStatusError("DeepSeek Payload Too Large", request=resp.request, response=resp)
            resp.raise_for_status()

            data = resp.json()
            raw_text = data["choices"][0]["message"]["content"]
            return json.loads(raw_text)


class DeterministicSemanticProvider(BaseLLMProvider):
    """
    Tier 4 / High-Reliability Fallback: Deterministic Regex & Semantic Parser.
    Extracts pricing models, employee counts, role families, dates, and entities
    without requiring external API tokens or incurring network latency.
    """

    def name(self) -> str:
        return "Deterministic Semantic Engine"

    def is_configured(self) -> bool:
        return True  # Always available

    async def extract_structured(self, prompt: str, schema_type: str) -> Dict[str, Any]:
        """Deterministic rule-based structural extractor."""
        text = prompt

        if schema_type == "STARTUP":
            # Extract employee count
            emp_match = re.search(r"(?:team\s*size|employees?|team\s*of)\s*[:=\-]?\s*(\d{1,6})", text, re.IGNORECASE)
            emp_count = int(emp_match.group(1)) if emp_match else None
            return {
                "employeeCount": emp_count,
            }

        elif schema_type == "PRODUCT":
            # Determine pricing model
            text_lower = text.lower()
            pricing = "PAID"
            if "free tier" in text_lower or "freemium" in text_lower or "get started free" in text_lower or "try for free" in text_lower:
                pricing = "FREEMIUM"
            elif "free" in text_lower and "pricing" not in text_lower and "paid" not in text_lower:
                pricing = "FREE"
            elif "enterprise" in text_lower or "contact sales" in text_lower or "custom pricing" in text_lower or "request demo" in text_lower:
                pricing = "ENTERPRISE"
            elif "$0" in text_lower:
                pricing = "FREEMIUM"
            return {
                "pricingModel": pricing,
            }

        elif schema_type == "JOB":
            text_lower = text.lower()
            # Remote detection
            is_remote = any(k in text_lower for k in ["remote", "work from home", "anywhere", "telecommute"])

            # Role family detection
            role_family = "Engineering"
            if any(k in text_lower for k in ["research", "scientist", "phd", "postdoc"]):
                role_family = "Research"
            elif any(k in text_lower for k in ["product manager", "pm", "head of product"]):
                role_family = "Product"
            elif any(k in text_lower for k in ["design", "ui", "ux", "frontend"]):
                role_family = "Design"
            elif any(k in text_lower for k in ["sales", "account executive", "growth", "business development"]):
                role_family = "Sales"
            elif any(k in text_lower for k in ["operations", "legal", "compliance", "people"]):
                role_family = "Operations"

            return {
                "is_remote": is_remote,
                "role_family": role_family,
            }

        return {}
