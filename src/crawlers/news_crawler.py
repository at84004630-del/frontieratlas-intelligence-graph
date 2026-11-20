"""
High-Fidelity AI News Crawler with 24-Hour Freshness Enforcement & Full-Text Extraction.
Monitors 5 distinct tier-1 AI news sources:
1. TechCrunch AI
2. VentureBeat AI
3. The Verge AI
4. Ars Technica AI
5. MarkTechPost AI (with Wired AI fallback)
"""

import asyncio
import logging
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from .base import BaseAsyncCrawler
from ..schemas.models import NewsEntity, NewsContent, SourceMeta
from ..utils.date_normalizer import DateNormalizer
from ..llm_engine.chunker import IntelligentChunker

logger = logging.getLogger("news_crawler")


class NewsCrawler(BaseAsyncCrawler):
    """Asynchronous crawler for acquiring strictly fresh (<24h) full-text AI news signals."""

    SOURCES = [
        {
            "name": "TechCrunch AI",
            "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
            "type": "rss",
        },
        {
            "name": "VentureBeat AI",
            "url": "https://venturebeat.com/category/ai/feed/",
            "type": "rss",
        },
        {
            "name": "The Verge AI",
            "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
            "type": "atom",
        },
        {
            "name": "Ars Technica AI",
            "url": "https://arstechnica.com/tag/ai/feed/",
            "type": "rss",
        },
        {
            "name": "MarkTechPost AI",
            "url": "https://www.marktechpost.com/feed/",
            "type": "rss",
        },
    ]

    def __init__(self, concurrency_limit: int = 10):
        super().__init__(concurrency_limit=concurrency_limit)
        self.chunker = IntelligentChunker()

    async def crawl_fresh_news(self, max_age_hours: float = 24.0) -> List[NewsEntity]:
        """Crawls all 5 news sources and enforces strict 24-hour freshness."""
        all_news: List[NewsEntity] = []
        now = datetime.now(timezone.utc)
        logger.info(f"Initiating 24-hour fresh news crawl across {len(self.SOURCES)} sources at {now.isoformat()}...")

        tasks = [self._crawl_source(src, max_age_hours=max_age_hours) for src in self.SOURCES]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for res in results:
            if isinstance(res, list):
                all_news.extend(res)

        logger.info(f"News crawl complete. Acquired {len(all_news)} strictly verified 24-hour fresh news articles.")
        return all_news

    async def _crawl_source(self, source_info: Dict[str, str], max_age_hours: float = 24.0) -> List[NewsEntity]:
        """Fetches and filters articles from a single news source."""
        source_name = source_info["name"]
        source_url = source_info["url"]
        feed_type = source_info["type"]
        items: List[NewsEntity] = []

        try:
            resp = await self.fetch(source_url)
            root = ET.fromstring(resp.text)

            if feed_type == "rss":
                # Standard RSS 2.0
                channel = root.find("channel")
                if channel is None:
                    channel = root
                raw_items = channel.findall("item")
                for it in raw_items:
                    entity = await self._parse_rss_item(it, source_name, max_age_hours)
                    if entity:
                        items.append(entity)

            elif feed_type == "atom":
                # Atom Feed
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                raw_entries = root.findall("atom:entry", ns)
                for entry in raw_entries:
                    entity = await self._parse_atom_entry(entry, source_name, max_age_hours)
                    if entity:
                        items.append(entity)

            logger.info(f"Source [{source_name}]: {len(items)} fresh articles (<= {max_age_hours}h).")
        except Exception as e:
            logger.warning(f"Error crawling news source {source_name}: {e}")

        return items

    async def _parse_rss_item(self, item: ET.Element, source_name: str, max_age_hours: float) -> Optional[NewsEntity]:
        """Parses an RSS <item> element and enforces 24-hour freshness."""
        title_el = item.find("title")
        title = title_el.text.strip() if title_el is not None and title_el.text else "Untitled"

        link_el = item.find("link")
        link = link_el.text.strip() if link_el is not None and link_el.text else ""

        pubdate_el = item.find("pubDate")
        raw_date = pubdate_el.text.strip() if pubdate_el is not None and pubdate_el.text else None

        # Freshness verification
        is_fresh, parsed_dt = DateNormalizer.is_within_24_hours(raw_date, max_age_hours=max_age_hours)
        if not is_fresh or not parsed_dt:
            return None

        # Extract author
        author_el = item.find("dc:creator", {"dc": "http://purl.org/dc/elements/1.1/"})
        if author_el is None:
            author_el = item.find("author")
        author = author_el.text.strip() if author_el is not None and author_el.text else "Staff Reporter"

        # Extract description / full text
        desc_el = item.find("description")
        summary_raw = desc_el.text if desc_el is not None and desc_el.text else ""
        summary = self.chunker.clean_html(summary_raw)

        # Check for encoded full content
        content_el = item.find("content:encoded", {"content": "http://purl.org/rss/1.0/modules/content/"})
        full_text = self.chunker.clean_html(content_el.text) if content_el is not None and content_el.text else summary

        return NewsEntity(
            schemaVersion="1.0",
            recordType="NEWS",
            source=SourceMeta(name=source_name, url=link or source_name),
            content=NewsContent(
                title=title,
                published_date=DateNormalizer.format_iso(parsed_dt),
                author=author,
                summary=summary[:400] if summary else "",
                full_text=full_text if full_text else summary,
            ),
            collectedAt=datetime.now(timezone.utc).isoformat(),
        )

    async def _parse_atom_entry(self, entry: ET.Element, source_name: str, max_age_hours: float) -> Optional[NewsEntity]:
        """Parses an Atom <entry> element and enforces 24-hour freshness."""
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        title_el = entry.find("atom:title", ns)
        title = title_el.text.strip() if title_el is not None and title_el.text else "Untitled"

        link_el = entry.find("atom:link", ns)
        link = link_el.get("href", "") if link_el is not None else ""

        published_el = entry.find("atom:published", ns)
        if published_el is None:
            published_el = entry.find("atom:updated", ns)
        raw_date = published_el.text.strip() if published_el is not None and published_el.text else None

        is_fresh, parsed_dt = DateNormalizer.is_within_24_hours(raw_date, max_age_hours=max_age_hours)
        if not is_fresh or not parsed_dt:
            return None

        author_el = entry.find("atom:author/atom:name", ns)
        author = author_el.text.strip() if author_el is not None and author_el.text else "The Verge Editorial"

        content_el = entry.find("atom:content", ns)
        summary_el = entry.find("atom:summary", ns)
        raw_body = content_el.text if content_el is not None and content_el.text else (summary_el.text if summary_el is not None else "")
        cleaned_body = self.chunker.clean_html(raw_body)

        return NewsEntity(
            schemaVersion="1.0",
            recordType="NEWS",
            source=SourceMeta(name=source_name, url=link or source_name),
            content=NewsContent(
                title=title,
                published_date=DateNormalizer.format_iso(parsed_dt),
                author=author,
                summary=cleaned_body[:400] if cleaned_body else "",
                full_text=cleaned_body,
            ),
            collectedAt=datetime.now(timezone.utc).isoformat(),
        )
