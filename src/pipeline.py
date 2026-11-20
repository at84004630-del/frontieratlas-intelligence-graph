"""
Master Pipeline Orchestrator for GraphOne / FrontierAtlas Intelligence Graph.
Coordinates concurrent ingestion, entity canonicalization, schema validation,
and automated multi-tab submission exports.
"""

import asyncio
import argparse
import sys
import os
import time
from typing import Dict, Any, List

from src.utils.logger import setup_logger
from src.entity_resolution.resolver import EntityResolver
from src.crawlers.startups_crawler import StartupsCrawler
from src.crawlers.products_crawler import ProductsCrawler
from src.crawlers.papers_crawler import PapersCrawler
from src.crawlers.news_crawler import NewsCrawler
from src.crawlers.jobs_crawler import JobsCrawler
from src.storage.exporter import DataExporter

logger = setup_logger("master_pipeline")


class MasterPipeline:
    """End-to-end data acquisition and normalization orchestrator."""

    def __init__(self, export_dir: str = "data/exports"):
        self.resolver = EntityResolver()
        self.exporter = DataExporter(export_dir=export_dir)

    async def run(
        self,
        target_startups: int = 1000,
        target_products: int = 1000,
        target_papers: int = 1000,
        max_freshness_hours: float = 24.0,
        run_startups: bool = True,
        run_products: bool = True,
        run_papers: bool = True,
        run_news: bool = True,
        run_jobs: bool = True,
    ) -> Dict[str, Any]:
        """Executes selected pipeline verticals concurrently."""
        start_time = time.time()
        logger.info("=" * 80)
        logger.info("STARTING GRAPHONE / FRONTIERATLAS GLOBAL INTELLIGENCE GRAPH PIPELINE")
        logger.info("=" * 80)

        startups = []
        products = []
        papers = []
        news = []
        jobs = []

        # -------------------------------------------------------------
        # Phase I: Massive One-Time Data Acquisition (Concurrent Crawl)
        # -------------------------------------------------------------
        crawlers_to_close = []

        if run_startups:
            sc = StartupsCrawler(self.resolver)
            crawlers_to_close.append(sc)
            logger.info(f"==> Launching Startups Crawler (target: {target_startups})...")
            startups = await sc.crawl_yc_companies(target_count=target_startups)

        if run_products:
            pc = ProductsCrawler(self.resolver)
            crawlers_to_close.append(pc)
            logger.info(f"==> Launching Products Crawler (target: {target_products})...")
            products = await pc.crawl_products(target_count=target_products)

        if run_papers:
            rc = PapersCrawler()
            crawlers_to_close.append(rc)
            logger.info(f"==> Launching Research Papers Crawler with GitHub Stars (target: {target_papers})...")
            papers = await rc.crawl_papers(target_count=target_papers)

        # -------------------------------------------------------------
        # Phase II: High-Fidelity Signal Ingestion (24h Fresh News & Jobs)
        # -------------------------------------------------------------
        if run_news:
            nc = NewsCrawler()
            crawlers_to_close.append(nc)
            logger.info(f"==> Launching 24-hr Fresh News Crawler (5 distinct sources)...")
            news = await nc.crawl_fresh_news(max_age_hours=max_freshness_hours)

        if run_jobs:
            jc = JobsCrawler(self.resolver)
            crawlers_to_close.append(jc)
            logger.info(f"==> Launching 24-hr Fresh Job Boards Crawler (5 distinct boards)...")
            jobs = await jc.crawl_fresh_jobs(max_age_hours=max_freshness_hours)

        # Clean up crawler connection pools
        for c in crawlers_to_close:
            await c.close()

        # Extract audit log
        mapping_logs = self.resolver.get_logs()

        # -------------------------------------------------------------
        # Phase III & Storage: Export to CSV and 6-Tab Google Sheets Workbook
        # -------------------------------------------------------------
        logger.info("==> Exporting all 6 dataset tabs...")
        export_paths = self.exporter.export_all(
            startups=startups,
            products=products,
            papers=papers,
            jobs=jobs,
            news=news,
            mapping_logs=mapping_logs,
        )

        elapsed = time.time() - start_time
        logger.info("=" * 80)
        logger.info("PIPELINE EXECUTION SUMMARY")
        logger.info(f"  • Startups Collected:       {len(startups):,}")
        logger.info(f"  • Products Collected:       {len(products):,}")
        logger.info(f"  • Research Papers:          {len(papers):,} (with GitHub stars)")
        logger.info(f"  • 24h Fresh News Articles:  {len(news):,}")
        logger.info(f"  • 24h Fresh Job Postings:   {len(jobs):,}")
        logger.info(f"  • Entity Resolution Events: {len(mapping_logs):,}")
        logger.info(f"  • Total Time Elapsed:       {elapsed:.2f} seconds")
        logger.info(f"  • Multi-Tab Excel Workbook: {export_paths.get('excel_workbook')}")
        logger.info("=" * 80)

        return {
            "startups": len(startups),
            "products": len(products),
            "papers": len(papers),
            "news": len(news),
            "jobs": len(jobs),
            "mapping_logs": len(mapping_logs),
            "paths": export_paths,
            "elapsed_seconds": elapsed,
        }


def main():
    parser = argparse.ArgumentParser(description="GraphOne / FrontierAtlas Global Intelligence Graph Pipeline")
    parser.add_argument("--startups", type=int, default=1000, help="Target startup count (default: 1000)")
    parser.add_argument("--products", type=int, default=1000, help="Target product count (default: 1000)")
    parser.add_argument("--papers", type=int, default=1000, help="Target research papers count (default: 1000)")
    parser.add_argument("--freshness", type=float, default=24.0, help="Maximum age in hours for news/jobs (default: 24.0)")
    parser.add_argument("--only-signals", action="store_true", help="Only run news and jobs signals")
    parser.add_argument("--only-entities", action="store_true", help="Only run startups, products, and papers")

    args = parser.parse_args()

    pipeline = MasterPipeline()

    run_startups = not args.only_signals
    run_products = not args.only_signals
    run_papers = not args.only_signals
    run_news = not args.only_entities
    run_jobs = not args.only_entities

    asyncio.run(
        pipeline.run(
            target_startups=args.startups,
            target_products=args.products,
            target_papers=args.papers,
            max_freshness_hours=args.freshness,
            run_startups=run_startups,
            run_products=run_products,
            run_papers=run_papers,
            run_news=run_news,
            run_jobs=run_jobs,
        )
    )


if __name__ == "__main__":
    main()
