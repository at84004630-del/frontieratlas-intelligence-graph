"""
High-Fidelity AI Job Boards Crawler with 24-Hour Freshness Enforcement.
Monitors 5 distinct tier-1 AI job boards:
1. RemoteOK AI
2. Jobicy AI
3. Remotive AI
4. Arbeitnow AI
5. Himalayas AI
Canonicalizes hiring companies, detects remote eligibility, and classifies role families.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from .base import BaseAsyncCrawler
from ..schemas.models import JobEntity, JobContent
from ..utils.date_normalizer import DateNormalizer
from ..entity_resolution.resolver import EntityResolver

logger = logging.getLogger("jobs_crawler")


class JobsCrawler(BaseAsyncCrawler):
    """Asynchronous crawler for acquiring strictly fresh (<24h) AI job postings."""

    def __init__(self, resolver: EntityResolver, concurrency_limit: int = 10):
        super().__init__(concurrency_limit=concurrency_limit)
        self.resolver = resolver

    async def crawl_fresh_jobs(self, max_age_hours: float = 24.0) -> List[JobEntity]:
        """Crawls all 5 job boards and strictly enforces 24-hour freshness."""
        all_jobs: List[JobEntity] = []
        logger.info(f"Initiating 24-hour fresh jobs crawl across 5 AI job boards (max age: {max_age_hours}h)...")

        tasks = [
            self._crawl_remoteok(max_age_hours),
            self._crawl_jobicy(max_age_hours),
            self._crawl_remotive(max_age_hours),
            self._crawl_arbeitnow(max_age_hours),
            self._crawl_himalayas(max_age_hours),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for res in results:
            if isinstance(res, list):
                all_jobs.extend(res)

        logger.info(f"Jobs crawl complete. Acquired {len(all_jobs)} strictly verified 24-hour fresh AI jobs.")
        return all_jobs

    def _classify_role_family(self, title: str, description: str = "") -> str:
        """Classifies role into canonical functional category."""
        text = f"{title} {description}".lower()
        if any(k in text for k in ["research", "scientist", "fellow", "postdoc", "phd", "alignment"]):
            return "Research"
        elif any(k in text for k in ["product manager", "pm", "head of product", "vp product"]):
            return "Product"
        elif any(k in text for k in ["design", "ui", "ux", "visual", "creative"]):
            return "Design"
        elif any(k in text for k in ["sales", "account executive", "growth", "business development", "revops"]):
            return "Sales"
        elif any(k in text for k in ["recruiter", "talent", "operations", "legal", "compliance", "finance"]):
            return "Operations"
        return "Engineering"

    # --- Board 1: RemoteOK ---
    async def _crawl_remoteok(self, max_age_hours: float) -> List[JobEntity]:
        url = "https://remoteok.com/api?tag=ai"
        jobs = []
        try:
            data = await self.fetch_json(url)
            if isinstance(data, list):
                for item in data:
                    if not isinstance(item, dict) or "company" not in item:
                        continue
                    raw_date = item.get("epoch") or item.get("date")
                    is_fresh, parsed_dt = DateNormalizer.is_within_24_hours(raw_date, max_age_hours=max_age_hours)
                    if not is_fresh or not parsed_dt:
                        continue

                    raw_company = item.get("company", "Unknown")
                    canonical_company, _, _ = self.resolver.resolve_startup(raw_company, entity_type="HIRING_COMPANY")

                    job_title = item.get("position", "AI Specialist")
                    jobs.append(
                        JobEntity(
                            schemaVersion="1.0",
                            recordType="JOB",
                            content=JobContent(
                                title=job_title,
                                company=canonical_company,
                                date=DateNormalizer.format_iso(parsed_dt),
                                is_remote=True,
                                role_family=self._classify_role_family(job_title, item.get("description", "")),
                                url=item.get("url") or f"https://remoteok.com/l/{item.get('id', '')}"
                            ),
                            collectedAt=datetime.now(timezone.utc).isoformat()
                        )
                    )
            logger.info(f"RemoteOK: {len(jobs)} fresh jobs.")
        except Exception as e:
            logger.warning(f"Error crawling RemoteOK: {e}")
        return jobs

    # --- Board 2: Jobicy ---
    async def _crawl_jobicy(self, max_age_hours: float) -> List[JobEntity]:
        url = "https://jobicy.com/api/v2/remote-jobs?tag=ai"
        jobs = []
        try:
            data = await self.fetch_json(url)
            if isinstance(data, dict):
                raw_jobs = data.get("jobs", [])
                for item in raw_jobs:
                    raw_date = item.get("pubDate")
                    is_fresh, parsed_dt = DateNormalizer.is_within_24_hours(raw_date, max_age_hours=max_age_hours)
                    if not is_fresh or not parsed_dt:
                        continue

                    raw_company = item.get("companyName", "Unknown")
                    canonical_company, _, _ = self.resolver.resolve_startup(raw_company, entity_type="HIRING_COMPANY")

                    title = item.get("jobTitle", "AI Engineer")
                    jobs.append(
                        JobEntity(
                            schemaVersion="1.0",
                            recordType="JOB",
                            content=JobContent(
                                title=title,
                                company=canonical_company,
                                date=DateNormalizer.format_iso(parsed_dt),
                                is_remote=True,
                                role_family=self._classify_role_family(title, item.get("jobDescription", "")),
                                url=item.get("url")
                            ),
                            collectedAt=datetime.now(timezone.utc).isoformat()
                        )
                    )
            logger.info(f"Jobicy: {len(jobs)} fresh jobs.")
        except Exception as e:
            logger.warning(f"Error crawling Jobicy: {e}")
        return jobs

    # --- Board 3: Remotive ---
    async def _crawl_remotive(self, max_age_hours: float) -> List[JobEntity]:
        url = "https://remotive.com/api/remote-jobs?category=software-dev&search=AI"
        jobs = []
        try:
            data = await self.fetch_json(url)
            if isinstance(data, dict):
                raw_jobs = data.get("jobs", [])
                for item in raw_jobs:
                    raw_date = item.get("publication_date")
                    is_fresh, parsed_dt = DateNormalizer.is_within_24_hours(raw_date, max_age_hours=max_age_hours)
                    if not is_fresh or not parsed_dt:
                        continue

                    raw_company = item.get("company_name", "Unknown")
                    canonical_company, _, _ = self.resolver.resolve_startup(raw_company, entity_type="HIRING_COMPANY")

                    title = item.get("title", "AI Engineer")
                    jobs.append(
                        JobEntity(
                            schemaVersion="1.0",
                            recordType="JOB",
                            content=JobContent(
                                title=title,
                                company=canonical_company,
                                date=DateNormalizer.format_iso(parsed_dt),
                                is_remote=True,
                                role_family=self._classify_role_family(title, item.get("description", "")),
                                url=item.get("url")
                            ),
                            collectedAt=datetime.now(timezone.utc).isoformat()
                        )
                    )
            logger.info(f"Remotive: {len(jobs)} fresh jobs.")
        except Exception as e:
            logger.warning(f"Error crawling Remotive: {e}")
        return jobs

    # --- Board 4: Arbeitnow ---
    async def _crawl_arbeitnow(self, max_age_hours: float) -> List[JobEntity]:
        url = "https://www.arbeitnow.com/api/job-board-api"
        jobs = []
        try:
            data = await self.fetch_json(url)
            if isinstance(data, dict):
                raw_jobs = data.get("data", [])
                for item in raw_jobs:
                    title = item.get("title", "")
                    tags = item.get("tags", [])
                    # Filter for AI/ML/Data roles
                    is_ai = any("ai" in str(t).lower() or "machine learning" in str(t).lower() or "data" in str(t).lower() for t in tags)
                    if not is_ai and "ai" not in title.lower():
                        continue

                    raw_date = item.get("created_at")
                    is_fresh, parsed_dt = DateNormalizer.is_within_24_hours(raw_date, max_age_hours=max_age_hours)
                    if not is_fresh or not parsed_dt:
                        continue

                    raw_company = item.get("company_name", "Unknown")
                    canonical_company, _, _ = self.resolver.resolve_startup(raw_company, entity_type="HIRING_COMPANY")

                    jobs.append(
                        JobEntity(
                            schemaVersion="1.0",
                            recordType="JOB",
                            content=JobContent(
                                title=title,
                                company=canonical_company,
                                date=DateNormalizer.format_iso(parsed_dt),
                                is_remote=bool(item.get("remote")),
                                role_family=self._classify_role_family(title, item.get("description", "")),
                                url=item.get("url")
                            ),
                            collectedAt=datetime.now(timezone.utc).isoformat()
                        )
                    )
            logger.info(f"Arbeitnow: {len(jobs)} fresh jobs.")
        except Exception as e:
            logger.warning(f"Error crawling Arbeitnow: {e}")
        return jobs

    # --- Board 5: Himalayas ---
    async def _crawl_himalayas(self, max_age_hours: float) -> List[JobEntity]:
        url = "https://himalayas.app/jobs/api?search=AI"
        jobs = []
        try:
            data = await self.fetch_json(url)
            if isinstance(data, dict):
                raw_jobs = data.get("jobs", [])
                for item in raw_jobs:
                    raw_date = item.get("pubDate") or item.get("publishedAt")
                    is_fresh, parsed_dt = DateNormalizer.is_within_24_hours(raw_date, max_age_hours=max_age_hours)
                    if not is_fresh or not parsed_dt:
                        continue

                    raw_company = item.get("companyName", "Unknown")
                    canonical_company, _, _ = self.resolver.resolve_startup(raw_company, entity_type="HIRING_COMPANY")

                    title = item.get("title", "AI Engineer")
                    jobs.append(
                        JobEntity(
                            schemaVersion="1.0",
                            recordType="JOB",
                            content=JobContent(
                                title=title,
                                company=canonical_company,
                                date=DateNormalizer.format_iso(parsed_dt),
                                is_remote=True,
                                role_family=self._classify_role_family(title, item.get("description", "")),
                                url=item.get("applicationUrl") or item.get("url")
                            ),
                            collectedAt=datetime.now(timezone.utc).isoformat()
                        )
                    )
            logger.info(f"Himalayas: {len(jobs)} fresh jobs.")
        except Exception as e:
            logger.warning(f"Error crawling Himalayas: {e}")
        return jobs
